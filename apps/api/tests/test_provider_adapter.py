"""The OpenAI-compatible adapter against a stub HTTP transport (no network, no key)."""

import json

import httpx2
import pytest

from app.providers.base import ProviderError
from app.providers.openai_compatible import OpenAICompatibleModel


def model(handler, base_url="http://llm.local/v1", key="secret-key"):  # type: ignore[no-untyped-def]
    return OpenAICompatibleModel(
        model="test-model",
        api_key=key,
        base_url=base_url,
        timeout_seconds=2,
        max_retries=0,
        http_client=httpx2.Client(transport=httpx2.MockTransport(handler)),
    )


def completion(message, finish="tool_calls"):  # type: ignore[no-untyped-def]
    return httpx2.Response(
        200,
        json={
            "id": "c1",
            "object": "chat.completion",
            "created": 1,
            "model": "test-model",
            "choices": [{"index": 0, "finish_reason": finish, "message": message}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        },
    )


def test_sends_tools_and_parses_tool_calls():
    seen = {}

    def handler(request):  # type: ignore[no-untyped-def]
        seen["url"] = str(request.url)
        seen["auth"] = request.headers.get("authorization")
        seen["body"] = json.loads(request.content)
        return completion(
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": "a",
                        "type": "function",
                        "function": {"name": "list_catalog_services", "arguments": "{}"},
                    }
                ],
            }
        )

    tools = [
        {
            "type": "function",
            "function": {
                "name": "list_catalog_services",
                "description": "d",
                "parameters": {"type": "object", "properties": {}},
            },
        }
    ]
    result = model(handler).complete([{"role": "user", "content": "hi"}], tools)
    assert seen["url"] == "http://llm.local/v1/chat/completions"
    assert seen["auth"] == "Bearer secret-key"
    assert seen["body"]["model"] == "test-model"
    assert seen["body"]["tool_choice"] == "auto"
    assert seen["body"]["tools"][0]["function"]["name"] == "list_catalog_services"
    assert (
        result.tool_calls[0].name == "list_catalog_services"
        and result.tool_calls[0].arguments == "{}"
    )


def test_text_reply_without_tools():
    result = model(
        lambda r: completion({"role": "assistant", "content": "hello"}, "stop")
    ).complete([], [])
    assert result.content == "hello" and result.tool_calls == []


@pytest.mark.parametrize(
    ("handler", "message"),
    [
        (lambda r: httpx2.Response(401, json={"error": {"message": "bad key"}}), "authentication"),
        (lambda r: httpx2.Response(429, json={"error": {"message": "slow"}}), "rate limited"),
        (lambda r: httpx2.Response(500, json={"error": {"message": "x"}}), "overloaded"),
        (lambda r: (_ for _ in ()).throw(httpx2.ReadTimeout("t", request=r)), "timeout"),
        (lambda r: (_ for _ in ()).throw(httpx2.ConnectError("c", request=r)), "connection"),
        (lambda r: completion({"role": "assistant", "content": "cut"}, "length"), "length"),
    ],
)
def test_failures_raise_provider_error(handler, message):
    with pytest.raises(ProviderError, match=message):
        model(handler).complete([{"role": "user", "content": "x"}], [])


def test_local_servers_work_without_a_key():
    seen = {}

    def handler(request):  # type: ignore[no-untyped-def]
        seen["auth"] = request.headers.get("authorization")
        return completion({"role": "assistant", "content": "ok"}, "stop")

    model(handler, base_url="http://localhost:11434/v1", key=None).complete([], [])
    assert seen["auth"] == "Bearer not-needed"


def test_configuration_rules(monkeypatch):
    from app.core.config import Settings

    assert not Settings(ai_model=None, ai_api_key="k", ai_provider_base_url=None).ai_configured
    assert not Settings(ai_model="m", ai_api_key=None, ai_provider_base_url=None).ai_configured
    assert Settings(ai_model="m", ai_api_key="k").ai_configured
    assert Settings(ai_model="m", ai_provider_base_url="http://localhost:11434/v1").ai_configured
    assert not Settings(ai_provider="disabled", ai_model="m", ai_api_key="k").ai_configured


def test_groq_tool_use_failed_becomes_a_retryable_rejection():
    from app.providers.base import ToolCallRejected

    def handler(request):  # type: ignore[no-untyped-def]
        return httpx2.Response(
            400,
            json={
                "error": {
                    "message": "Tool call validation failed: missing properties",
                    "type": "invalid_request_error",
                    "code": "tool_use_failed",
                }
            },
        )

    with pytest.raises(ToolCallRejected, match="missing properties"):
        model(handler).complete([{"role": "user", "content": "x"}], [])


def test_optional_reasoning_and_output_settings_are_sent_only_when_set():
    seen = {}

    def handler(request):  # type: ignore[no-untyped-def]
        seen.update(json.loads(request.content))
        return completion({"role": "assistant", "content": "ok"}, "stop")

    model(handler).complete([], [])
    assert "reasoning_effort" not in seen and "max_completion_tokens" not in seen
    OpenAICompatibleModel(
        model="m",
        api_key="k",
        base_url="http://llm.local/v1",
        timeout_seconds=2,
        max_retries=0,
        http_client=httpx2.Client(transport=httpx2.MockTransport(handler)),
        reasoning_effort="low",
        max_output_tokens=2000,
    ).complete([], [])
    assert seen["reasoning_effort"] == "low" and seen["max_completion_tokens"] == 2000


def test_rate_limits_fail_over_to_the_next_model_then_wait_once():
    calls = []
    sleeps = []

    def handler(request):  # type: ignore[no-untyped-def]
        name = json.loads(request.content)["model"]
        calls.append(name)
        if name == "a" or len(calls) <= 2:
            return httpx2.Response(
                429, headers={"retry-after": "3"}, json={"error": {"message": "slow down"}}
            )
        return completion({"role": "assistant", "content": "ok"}, "stop")

    m = OpenAICompatibleModel(
        model="a, b",
        api_key="k",
        base_url="http://llm.local/v1",
        timeout_seconds=2,
        max_retries=3,
        http_client=httpx2.Client(transport=httpx2.MockTransport(handler)),
        sleep=sleeps.append,
    )
    assert m.complete([], []).content == "ok"
    assert calls == ["a", "b", "a", "b"] and sleeps == [3.0]


def test_all_models_limited_after_waiting_is_an_error():
    m = OpenAICompatibleModel(
        model="a,b",
        api_key="k",
        base_url="http://llm.local/v1",
        timeout_seconds=2,
        max_retries=0,
        http_client=httpx2.Client(
            transport=httpx2.MockTransport(lambda r: httpx2.Response(429, json={}))
        ),
        sleep=lambda s: None,
    )
    with pytest.raises(ProviderError, match="rate limited"):
        m.complete([], [])
