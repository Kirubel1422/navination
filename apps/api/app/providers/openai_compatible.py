"""OpenAI-compatible Chat Completions adapter (OpenAI, Azure OpenAI, vLLM, Ollama, LM Studio, ...).

Uses the official `openai` SDK with function tools. Only widely supported parameters are sent
(no temperature, max tokens or parallel-tool flags) so the adapter works across compatible
servers. Every failure is raised as ProviderError; callers decide how to report it.
"""

import logging
import time
from typing import Any

import httpx2
import openai

from app.providers.base import AssistantTurn, ProviderError, ToolCall, ToolCallRejected

DEFAULT_BASE_URL = "https://api.openai.com/v1"
logger = logging.getLogger("navination.model")


MAX_RATE_LIMIT_WAIT_SECONDS = 20.0


class OpenAICompatibleModel:
    """`model` may be a comma-separated list. On a rate limit or a 5xx overload the next model is tried (each model
    usually has its own quota); only when every model is limited does it wait once, honouring
    Retry-After up to MAX_RATE_LIMIT_WAIT_SECONDS."""

    def __init__(
        self,
        model: str,
        api_key: str | None,
        base_url: str | None,
        timeout_seconds: float,
        max_retries: int,
        http_client: httpx2.Client | None = None,
        reasoning_effort: str | None = None,
        max_output_tokens: int | None = None,
        sleep: Any = time.sleep,
    ) -> None:
        self.models = [m.strip() for m in model.split(",") if m.strip()]
        self.name = self.models[0]
        self._sleep = sleep
        self.extra: dict[str, Any] = {}
        if reasoning_effort:
            self.extra["reasoning_effort"] = reasoning_effort
        if max_output_tokens:
            self.extra["max_completion_tokens"] = max_output_tokens
        self.client = openai.OpenAI(
            # Local servers often ignore the key, but the SDK requires a value.
            api_key=api_key or "not-needed",
            base_url=base_url or DEFAULT_BASE_URL,
            timeout=timeout_seconds,
            # With several models, fail over immediately instead of letting the SDK sleep.
            max_retries=max_retries if len(self.models) == 1 else 0,
            http_client=http_client,
        )

    def complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        response_format: dict[str, Any] | None = None,
    ) -> AssistantTurn:
        waited = False
        while True:
            waits: list[float] = []
            for model in self.models:
                try:
                    return self._complete_once(model, messages, tools, response_format)
                except _RateLimited as limited:
                    logger.info("model=%s rate limited, retry-after=%s", model, limited.retry_after)
                    waits.append(limited.retry_after)
            if waited or len(self.models) == 1:
                raise ProviderError("model rate limited or overloaded")
            self._sleep(min(min(waits), MAX_RATE_LIMIT_WAIT_SECONDS))
            waited = True

    def _complete_once(
        self,
        model: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        response_format: dict[str, Any] | None,
    ) -> AssistantTurn:
        kwargs: dict[str, Any] = dict(self.extra)
        if tools:  # an empty tools array is rejected by some servers
            kwargs.update(tools=tools, tool_choice="auto")
        if response_format is not None:
            kwargs["response_format"] = response_format
        try:
            response = self.client.chat.completions.create(
                model=model,
                messages=messages,  # type: ignore[arg-type]
                **kwargs,
            )
        except openai.APITimeoutError as exc:
            raise ProviderError("model timeout") from exc
        except openai.APIConnectionError as exc:
            raise ProviderError("model connection failure") from exc
        except openai.RateLimitError as exc:
            raise _RateLimited(_retry_after(exc)) from exc
        except openai.AuthenticationError as exc:
            raise ProviderError("model authentication failed") from exc
        except openai.BadRequestError as exc:
            body = exc.body
            if isinstance(body, list) and body:  # Gemini wraps the error object in a list
                body = body[0]
            body = body if isinstance(body, dict) else {}
            error = body.get("error", body) if isinstance(body, dict) else {}
            if isinstance(error, dict) and error.get("code") == "tool_use_failed":
                raise ToolCallRejected(
                    str(error.get("message", "invalid tool call"))[:500]
                ) from exc
            logger.warning(
                "model=%s bad request: %s",
                model,
                str(error.get("message", "") if isinstance(error, dict) else "")[:300]
                or str(exc)[:300],
            )
            raise ProviderError("model status 400") from exc
        except openai.APIStatusError as exc:
            if exc.status_code == 413:  # request larger than the provider's per-request limit
                raise _RateLimited(5.0) from exc
            if exc.status_code in (500, 502, 503, 504):  # overloaded: try the next model
                logger.info("model=%s status %s", model, exc.status_code)
                raise _RateLimited(3.0) from exc
            raise ProviderError(f"model status {exc.status_code}") from exc
        except openai.OpenAIError as exc:
            raise ProviderError(f"model error: {type(exc).__name__}") from exc

        usage = response.usage
        if usage is not None:
            logger.info(
                "model=%s tokens in=%s out=%s", model, usage.prompt_tokens, usage.completion_tokens
            )
        if not response.choices:
            raise ProviderError("model returned no choices")
        choice = response.choices[0]
        if choice.finish_reason in ("length", "content_filter"):
            raise ProviderError(f"model finish_reason {choice.finish_reason}")
        message = choice.message
        calls = [
            ToolCall(
                id=call.id,
                name=call.function.name,
                arguments=call.function.arguments or "{}",
                extra=call.model_extra or None,
            )
            for call in (message.tool_calls or [])
            if getattr(call, "type", "function") == "function"
        ]
        return AssistantTurn(content=message.content, tool_calls=calls)


class _RateLimited(Exception):
    def __init__(self, retry_after: float) -> None:
        super().__init__(f"rate limited ({retry_after}s)")
        self.retry_after = retry_after


def _retry_after(exc: openai.APIStatusError) -> float:
    try:
        return max(0.5, float(exc.response.headers.get("retry-after", "5")))
    except (TypeError, ValueError):
        return 5.0
