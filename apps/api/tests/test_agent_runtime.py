import json

import pytest
from pydantic import BaseModel, ConfigDict

from app.agent.runtime import AgentError, FinishTool, Tool, ToolError, inline_schema, run_agent
from app.providers.base import ProviderError
from tests.fakes import QueueModel, call, tool_results, turn


class Answer(BaseModel):
    model_config = ConfigDict(extra="forbid")
    value: int


def run(model, check=lambda a: [], tools=None, max_steps=6, mode="tool", research=True):  # type: ignore[no-untyped-def]
    echo = Tool(
        "echo",
        "Echo",
        {"type": "object", "properties": {"x": {"type": "string"}}},
        lambda a: {"echo": a.get("x")},
    )

    def broken(_):  # type: ignore[no-untyped-def]
        raise ToolError("tool is down")

    return run_agent(
        model,
        system="sys",
        user="{}",
        tools=tools
        if tools is not None
        else [echo, Tool("broken", "x", {"type": "object", "properties": {}}, broken)],
        finish=FinishTool("submit", "Submit", Answer, check),
        max_steps=max_steps,
        deadline_seconds=30,
        structured_output=mode,
        research=research,
    )


def test_tools_then_submit():
    model = QueueModel(turn(call("echo", {"x": "hi"})), turn(call("submit", {"value": 3})))
    assert run(model).value == 3
    messages, tools = model.requests[1]
    assert {t["function"]["name"] for t in tools} == {"echo", "broken", "submit"}
    assert tool_results(messages) == [{"echo": "hi"}]
    assistant = [m for m in messages if m["role"] == "assistant"][0]
    assert assistant["tool_calls"][0]["function"]["name"] == "echo"


def test_errors_are_returned_to_the_model_so_it_can_recover():
    model = QueueModel(
        turn(call("broken", {}), call("nope", {}), call("echo", "not json")),
        turn(call("submit", {"value": "x"})),
        turn(call("submit", {"value": 1, "extra": True})),
        turn(call("submit", {"value": 7})),
    )
    assert run(model, check=lambda a: [] if a.value == 7 else ["value must be 7"]).value == 7
    results = tool_results(model.requests[1][0])
    assert results[0] == {"error": "tool is down"}
    assert results[1] == {"error": "Unknown tool nope"}
    assert "not valid JSON" in results[2]["error"]
    rejected = tool_results(model.requests[2][0])[-1]
    assert rejected["error"] == "Submission rejected"


def test_semantic_check_rejection_then_success():
    model = QueueModel(turn(call("submit", {"value": 1})), turn(call("submit", {"value": 7})))
    assert run(model, check=lambda a: [] if a.value == 7 else ["value must be 7"]).value == 7
    assert tool_results(model.requests[1][0])[-1]["problems"] == ["value must be 7"]


def test_nudges_then_gives_up_without_submission():
    model = QueueModel(turn(content="hello"), turn(content="still"), turn(content="no"))
    with pytest.raises(AgentError, match="did not call the submit tool"):
        run(model)


def test_step_budget_and_provider_errors():
    with pytest.raises(AgentError, match="budget"):
        run(QueueModel(*[turn(call("echo", {"x": "a"})) for _ in range(3)]), max_steps=3)
    with pytest.raises(AgentError, match="timeout"):
        run(QueueModel(ProviderError("model timeout")))


def test_inline_schema_has_no_refs_or_titles():
    from app.agent.drafts import DiscoveryDraft, PlanDraft

    for model in (DiscoveryDraft, PlanDraft):
        schema = inline_schema(model)
        text = json.dumps(schema)
        assert "$ref" not in text and "$defs" not in text
        assert "title" not in schema  # annotation titles are dropped...
    plan = inline_schema(PlanDraft)
    assert "title" in plan["properties"]  # ...but a field named "title" is kept
    step = plan["properties"]["stages"]["items"]["properties"]["steps"]["items"]
    assert {"title", "instructions", "assessment"} <= set(step["required"])


def test_provider_side_tool_validation_errors_are_retried():
    from app.providers.base import ToolCallRejected

    model = QueueModel(
        ToolCallRejected("missing properties: 'value'"), turn(call("submit", {"value": 2}))
    )
    assert run(model).value == 2
    retry_prompt = model.requests[1][0][-1]
    assert retry_prompt["role"] == "user" and "rejected" in retry_prompt["content"]
    with pytest.raises(AgentError, match="invalid answers"):
        run(QueueModel(*[ToolCallRejected("bad") for _ in range(4)]))


def test_submit_schema_uses_refs_by_default():
    model = QueueModel(turn(call("submit", {"value": 1})))
    run(model)
    submit = next(t for t in model.requests[0][1] if t["function"]["name"] == "submit")
    assert "maxLength" not in json.dumps(submit) and "title" not in submit["function"]["parameters"]


# ---------------------------------------------------------------- json_schema protocol


def answer(value):  # type: ignore[no-untyped-def]
    return turn(content=json.dumps({"value": value}))


def test_json_mode_researches_with_tools_then_answers_with_a_strict_schema():
    model = QueueModel(
        turn(call("echo", {"x": "a"})),
        turn(content="I have enough information."),
        answer(5),
    )
    assert run(model, mode="json_schema").value == 5
    research_tools = {t["function"]["name"] for t in model.requests[0][1]}
    assert research_tools == {"echo", "broken"}  # no submit tool in json mode
    assert model.formats[0] is None and model.formats[1] is None
    final_tools, final_format = model.requests[2][1], model.formats[2]
    assert final_tools == []  # providers like Groq cannot combine tools with response_format
    assert final_format["type"] == "json_schema" and final_format["json_schema"]["strict"] is True
    schema = final_format["json_schema"]["schema"]
    assert schema["required"] == ["value"] and schema["additionalProperties"] is False


def test_json_mode_rejections_are_sent_back_and_corrected():
    model = QueueModel(turn(content="not json"), answer("x"), answer(1), answer(7))
    assert (
        run(
            model,
            mode="json_schema",
            research=False,
            check=lambda a: [] if a.value == 7 else ["value must be 7"],
        ).value
        == 7
    )
    feedback = [m["content"] for m in model.requests[-1][0] if m["role"] == "user"][1:]
    assert len(feedback) == 3 and all(f.startswith("Your answer was rejected") for f in feedback)
    assert "value must be 7" in feedback[-1]


def test_json_mode_without_research_answers_in_one_call():
    model = QueueModel(turn(content='```json\n{"value": 3}\n```'))
    assert run(model, mode="json_schema", research=False).value == 3
    assert len(model.requests) == 1 and model.formats[0] is not None


def test_json_mode_malformed_research_call_moves_on_to_answering():
    from app.providers.base import ToolCallRejected

    model = QueueModel(ToolCallRejected("attempted to call tool 'commentary'"), answer(2))
    assert run(model, mode="json_schema").value == 2
    assert model.formats == [None, model.formats[1]] and model.formats[1] is not None


def test_strict_schema_makes_every_property_required_and_closed():
    from app.agent.drafts import DiscoveryDraft
    from app.agent.runtime import strict_schema

    schema = strict_schema(DiscoveryDraft)
    text = json.dumps(schema)
    assert "$ref" not in text and "maxLength" not in text and "pattern" not in text

    def walk(node):  # type: ignore[no-untyped-def]
        if isinstance(node, dict):
            if node.get("type") == "object" and "properties" in node:
                assert set(node["required"]) == set(node["properties"])
                assert node["additionalProperties"] is False
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(schema)
