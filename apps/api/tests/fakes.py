"""Programmable test doubles for the agent: models and an in-memory official web."""

import json
from collections.abc import Callable
from itertools import count
from typing import Any

import httpx

from app.agent.web import OfficialWeb
from app.core.config import get_settings
from app.providers.base import AssistantTurn, ProviderError, ToolCall
from devtools.scripted_model import ScriptedModel

_ids = count(1)


def call(name: str, args: dict[str, Any] | str) -> ToolCall:
    text = args if isinstance(args, str) else json.dumps(args, ensure_ascii=False)
    return ToolCall(id=f"t{next(_ids)}", name=name, arguments=text)


def turn(*calls: ToolCall, content: str | None = None) -> AssistantTurn:
    return AssistantTurn(content=content, tool_calls=list(calls))


def tool_results(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for m in messages:
        if m.get("role") == "tool":
            try:
                out.append(json.loads(m["content"]))
            except json.JSONDecodeError:
                out.append({"raw": m["content"]})
    return out


Format = dict[str, Any] | None


def was_rejected(messages: list[dict[str, Any]]) -> bool:
    """True once the runtime has rejected an answer (tool error or follow-up message)."""
    if any(r.get("error") == "Submission rejected" for r in tool_results(messages)):
        return True
    return any(
        m.get("role") == "user" and str(m.get("content", "")).startswith("Your answer was rejected")
        for m in messages
    )


class QueueModel:
    """Returns the queued turns in order; records every request it receives."""

    name = "queue-model"

    def __init__(self, *turns: AssistantTurn | Exception) -> None:
        self.turns = list(turns)
        self.requests: list[tuple[list[dict[str, Any]], list[dict[str, Any]]]] = []
        self.formats: list[Format] = []

    def complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        response_format: Format = None,
    ) -> AssistantTurn:
        self.requests.append(([dict(m) for m in messages], tools))
        self.formats.append(response_format)
        if not self.turns:
            raise ProviderError("queue exhausted")
        item = self.turns.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


class RecordingModel:
    """Wraps the scripted model and records the payload of every agent run."""

    name = "recording-model"

    def __init__(self, inner: Any | None = None) -> None:
        self.inner = inner or ScriptedModel()
        self.payloads: list[dict[str, Any]] = []
        self.systems: list[str] = []

    def complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        response_format: Format = None,
    ) -> AssistantTurn:
        if len(messages) == 2:
            self.systems.append(messages[0]["content"])
            self.payloads.append(json.loads(messages[1]["content"]))
        return self.inner.complete(messages, tools, response_format)


class HookModel:
    """Scripted model with a hook that may replace any turn (e.g. to submit something invalid).

    Answers are shown to the hook as submit-tool calls whatever the protocol, and converted back
    to JSON content when the runtime asked for a structured answer."""

    name = "hook-model"

    def __init__(
        self,
        hook: Callable[
            [list[dict[str, Any]], list[dict[str, Any]], AssistantTurn], AssistantTurn | None
        ],
    ):
        self.inner = ScriptedModel()
        self.hook = hook

    def complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        response_format: Format = None,
    ) -> AssistantTurn:
        default = self.inner.complete(messages, tools, response_format)
        name = (response_format or {}).get("json_schema", {}).get("name")
        if name and default.content and not default.tool_calls:
            default = AssistantTurn(content=None, tool_calls=[call(name, default.content)])
        result = self.hook(messages, tools, default) or default
        if name:
            submitted = next((c for c in result.tool_calls if c.name == name), None)
            if submitted is not None:
                return AssistantTurn(content=submitted.arguments)
        return result


def fake_web(
    pages: dict[str, tuple[int, str, dict[str, str]]], search: list[dict[str, str]] | None = None
) -> OfficialWeb:
    """OfficialWeb over an in-memory transport: url -> (status, body, headers)."""

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if url.startswith("https://api.tavily.com"):
            return httpx.Response(200, json={"results": search or []})
        status, body, headers = pages.get(url, (404, "missing", {"content-type": "text/html"}))
        return httpx.Response(status, text=body, headers=headers)

    settings = get_settings().model_copy(
        update={
            "web_fetch_enabled": True,
            "web_search_provider": "tavily",
            "web_search_api_key": "k",
        }
        if search is not None
        else {"web_fetch_enabled": True}
    )
    return OfficialWeb(settings, client=httpx.Client(transport=httpx.MockTransport(handler)))


def html(title: str, body: str) -> tuple[int, str, dict[str, str]]:
    return (
        200,
        f"<html><head><title>{title}</title><script>evil()</script></head><body><p>{body}</p></body></html>",
        {"content-type": "text/html; charset=utf-8"},
    )
