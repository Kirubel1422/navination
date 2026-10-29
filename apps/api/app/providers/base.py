"""Provider-neutral chat-model contract used by the agent runtime."""

from dataclasses import dataclass, field
from typing import Any, Protocol


class ProviderError(Exception):
    """Timeout, transport failure, refusal, truncation or an unusable response."""


class ToolCallRejected(ProviderError):
    """The provider itself rejected the model's output as invalid: a malformed tool call or JSON
    that does not match the requested schema (Groq `tool_use_failed` / `json_validate_failed`).

    The agent loop treats this like a rejected submission and asks the model to try again.
    """


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    arguments: str  # raw JSON text exactly as produced by the model
    # Provider-specific fields that must be echoed back with the call (e.g. Gemini's
    # `extra_content.google.thought_signature`, which Gemini 3 requires on the next turn).
    extra: dict[str, Any] | None = None


@dataclass(frozen=True)
class AssistantTurn:
    content: str | None
    tool_calls: list[ToolCall] = field(default_factory=list)


class ChatModel(Protocol):
    """One model round trip: chat messages plus function-tool specs in, one assistant turn out."""

    name: str

    def complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        response_format: dict[str, Any] | None = None,
    ) -> AssistantTurn: ...
