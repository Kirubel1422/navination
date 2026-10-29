"""A small, bounded tool-calling agent loop.

The model may call read-only tools any number of times (within the step and time budget) and
must finish by calling the run's `submit_*` tool. The submission is validated twice: against its
JSON schema (Pydantic) and against semantic checks (known IDs, sources the agent actually read).
Problems are returned to the model as tool errors so it can correct itself.
"""

import json
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ValidationError

from app.providers.base import ChatModel, ProviderError, ToolCallRejected

logger = logging.getLogger("navination.agent")
MAX_TOOL_RESULT_CHARS = 12_000
MAX_NUDGES = 2
MAX_REJECTIONS = 3


class AgentError(Exception):
    """The agent could not produce a valid result (provider failure, budget or invalid output)."""


class ToolError(Exception):
    """A tool failed in a way the model should see and can work around."""


@dataclass
class Tool:
    name: str
    description: str
    parameters: dict[str, Any]
    handler: Callable[[dict[str, Any]], Any]


@dataclass
class FinishTool[T: BaseModel]:
    name: str
    description: str
    model: type[T]
    check: Callable[[T], list[str]] = lambda _: []


@dataclass
class WebSource:
    url: str
    title: str
    publisher: str
    fetched_at: datetime


@dataclass
class AgentStep:
    tool: str
    detail: str


@dataclass
class AgentContext:
    """Per-run state shared with tools: the activity trace and pages the agent actually read."""

    trace: list[AgentStep] = field(default_factory=list)
    read_pages: dict[str, WebSource] = field(default_factory=dict)
    # Text of pages read in this run, so contact numbers can be checked against what was read.
    page_texts: dict[str, str] = field(default_factory=dict)
    # Service centres returned by the places tool in this run (id -> place); only these may be cited.
    places: dict[str, Any] = field(default_factory=dict)
    # The person's location for this run only (never stored), and the emirate bias otherwise.
    location: tuple[float, float] | None = None
    emirate: str | None = None

    def record(self, tool: str, detail: str) -> None:
        self.trace.append(AgentStep(tool=tool, detail=detail[:200]))


def inline_schema(model: type[BaseModel]) -> dict[str, Any]:
    """JSON schema without $ref/$defs/titles, which some OpenAI-compatible servers reject."""
    schema = model.model_json_schema()
    defs = schema.pop("$defs", {})

    def resolve(node: Any, is_properties: bool = False) -> Any:
        if isinstance(node, dict):
            if "$ref" in node:
                return resolve(defs[node["$ref"].split("/")[-1]])
            if is_properties:  # keys are field names (a field may be called "title")
                return {k: resolve(v) for k, v in node.items()}
            return {
                k: resolve(v, is_properties=(k == "properties"))
                for k, v in node.items()
                if k not in ("title", "default")
            }
        if isinstance(node, list):
            return [resolve(item) for item in node]
        return node

    return resolve(schema)


# Constraints the backend enforces anyway when it validates a submission; leaving them out of the
# schema sent to the model saves a large share of the prompt on every call.
_VALIDATION_ONLY = {
    "minLength",
    "maxLength",
    "minItems",
    "maxItems",
    "pattern",
    "additionalProperties",
}


def compact_schema(node: Any, is_properties: bool = False) -> Any:
    if isinstance(node, dict):
        if is_properties:
            return {k: compact_schema(v) for k, v in node.items()}
        return {
            k: compact_schema(v, is_properties=(k == "properties"))
            for k, v in node.items()
            if k not in _VALIDATION_ONLY
        }
    if isinstance(node, list):
        return [compact_schema(item) for item in node]
    return node


def referenced_schema(model: type[BaseModel]) -> dict[str, Any]:
    """JSON schema keeping $defs/$ref (smaller); only annotation titles and defaults removed."""

    def strip(node: Any, is_properties: bool = False) -> Any:
        if isinstance(node, dict):
            if is_properties:
                return {k: strip(v) for k, v in node.items()}
            return {
                k: strip(v, is_properties=(k == "properties"))
                for k, v in node.items()
                if k not in ("title", "default")
            }
        if isinstance(node, list):
            return [strip(item) for item in node]
        return node

    return strip(model.model_json_schema())


def tool_spec(name: str, description: str, parameters: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {"name": name, "description": description, "parameters": parameters},
    }


def _dump(value: Any) -> str:
    text = json.dumps(value, ensure_ascii=False, default=str)
    if len(text) > MAX_TOOL_RESULT_CHARS:
        text = text[:MAX_TOOL_RESULT_CHARS] + "…[truncated]"
    return text


def _format_validation(error: ValidationError) -> list[str]:
    problems = []
    for item in error.errors()[:15]:
        where = ".".join(str(part) for part in item.get("loc", ()))
        problems.append(f"{where or 'input'}: {item.get('msg', 'invalid')}")
    return problems


def strict_schema(model: type[BaseModel]) -> dict[str, Any]:
    """Inlined schema for strict structured outputs: every property required (optional ones are
    nullable), no extra properties, and only keywords strict decoders support."""

    def walk(node: Any, is_properties: bool = False) -> Any:
        if isinstance(node, dict):
            if is_properties:
                return {k: walk(v) for k, v in node.items()}
            out = {
                k: walk(v, is_properties=(k == "properties"))
                for k, v in node.items()
                if k not in _VALIDATION_ONLY and k not in ("description",)
            }
            if out.get("type") == "object" and "properties" in out:
                out["required"] = list(out["properties"])
                out["additionalProperties"] = False
            return out
        if isinstance(node, list):
            return [walk(item) for item in node]
        return node

    return walk(inline_schema(model))


def _parse_json_content(text: str) -> Any:
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        text = text[text.find("{") :] if "{" in text else text
    return json.loads(text)


MAX_RESEARCH_TURNS = 6


def run_agent[T: BaseModel](
    model: ChatModel,
    *,
    system: str,
    user: str,
    tools: list[Tool],
    finish: FinishTool[T],
    max_steps: int,
    deadline_seconds: float,
    inline_refs: bool = False,
    structured_output: str = "json_schema",
    research: bool = True,
) -> T:
    """Run one agent task.

    json_schema mode (default): an optional research phase offers only the read-only tools; when
    the model replies without tool calls (or after MAX_RESEARCH_TURNS) the answer phase asks for
    the final answer with a strict JSON schema and no tools. Providers such as Groq cannot combine
    the two in one request, and constrained decoding is far more reliable for large answers.

    tool mode: the final answer is a call to the `submit_*` tool offered alongside the others.

    In both modes any submission (JSON content or a submit-tool call) is validated against the
    schema and the semantic checks; problems are sent back to the model to fix.
    """
    by_name = {t.name: t for t in tools}
    research_specs = [tool_spec(t.name, t.description, t.parameters) for t in tools]
    if structured_output == "tool":
        schema = inline_schema(finish.model) if inline_refs else referenced_schema(finish.model)
        research_specs.append(tool_spec(finish.name, finish.description, compact_schema(schema)))
    response_format = {
        "type": "json_schema",
        "json_schema": {"name": finish.name, "schema": strict_schema(finish.model), "strict": True},
    }
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
    researching = structured_output == "tool" or (research and bool(tools))
    research_turns = 0
    started = time.monotonic()
    nudges = 0
    rejections = 0

    def reject(problems: list[str], content: str | None) -> None:
        nonlocal rejections
        rejections += 1
        logger.info("agent submission rejected: %s", problems[:3])
        if rejections > MAX_REJECTIONS:
            raise AgentError("model kept producing invalid answers")
        if content is not None:
            messages.append({"role": "assistant", "content": content})
        messages.append(
            {
                "role": "user",
                "content": "Your answer was rejected. Fix these problems and answer again:\n- "
                + "\n- ".join(problems[:15]),
            }
        )

    def validate(arguments: Any) -> tuple[T | None, list[str]]:
        try:
            submission = finish.model.model_validate(arguments)
        except ValidationError as exc:
            return None, _format_validation(exc)
        problems = finish.check(submission)
        return (submission, []) if not problems else (None, problems)

    for _ in range(max_steps):
        if time.monotonic() - started > deadline_seconds:
            raise AgentError("agent deadline exceeded")
        answer_phase = structured_output != "tool" and not researching
        try:
            if answer_phase:
                turn = model.complete(messages, [], response_format)
            else:
                turn = model.complete(messages, research_specs)
        except ToolCallRejected as exc:
            logger.info("provider rejected the model output: %s", str(exc)[:400])
            if not answer_phase and structured_output != "tool":
                researching = False  # a malformed research call: move on to answering
                continue
            reject([str(exc)], None)
            continue
        except ProviderError as exc:
            raise AgentError(str(exc)) from exc

        if not turn.tool_calls:
            if answer_phase:
                try:
                    arguments = _parse_json_content(turn.content or "")
                except json.JSONDecodeError:
                    reject(
                        ["The answer must be a single JSON object matching the schema."],
                        turn.content or "",
                    )
                    continue
                submission, problems = validate(arguments)
                if submission is not None:
                    return submission
                reject(problems, turn.content or "")
                continue
            if structured_output == "tool":
                nudges += 1
                if nudges > MAX_NUDGES:
                    raise AgentError("model did not call the submit tool")
                messages.append({"role": "assistant", "content": turn.content or ""})
                messages.append(
                    {
                        "role": "user",
                        "content": f"Use the tools if needed, then call `{finish.name}` with your final answer.",
                    }
                )
                continue
            # Research finished: the model replied without calling a tool.
            if turn.content:
                messages.append({"role": "assistant", "content": turn.content})
                # Some providers (Gemini) reject a request that ends with a model turn.
                messages.append({"role": "user", "content": "Now give your final answer as JSON."})
            researching = False
            continue

        messages.append(
            {
                "role": "assistant",
                "content": turn.content,
                "tool_calls": [
                    {
                        **(call.extra or {}),
                        "id": call.id,
                        "type": "function",
                        "function": {"name": call.name, "arguments": call.arguments},
                    }
                    for call in turn.tool_calls
                ],
            }
        )
        for call in turn.tool_calls:
            try:
                arguments = json.loads(call.arguments or "{}")
                if not isinstance(arguments, dict):
                    raise ValueError("arguments must be a JSON object")
            except (json.JSONDecodeError, ValueError) as exc:
                result: Any = {"error": f"Arguments were not valid JSON: {exc}"}
            else:
                if call.name == finish.name:
                    submission, problems = validate(arguments)
                    if submission is not None:
                        return submission
                    logger.info("agent submission rejected: %s", problems[:3])
                    result = {"error": "Submission rejected", "problems": problems[:15]}
                elif call.name in by_name:
                    try:
                        result = by_name[call.name].handler(arguments)
                    except ToolError as exc:
                        result = {"error": str(exc)}
                else:
                    result = {"error": f"Unknown tool {call.name}"}
            messages.append({"role": "tool", "tool_call_id": call.id, "content": _dump(result)})
        research_turns += 1
        if structured_output != "tool" and research_turns >= MAX_RESEARCH_TURNS:
            researching = False

    raise AgentError("agent step budget exhausted")
