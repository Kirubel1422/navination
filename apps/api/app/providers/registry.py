"""Selects the configured chat model. Returns None when no model is configured."""

from functools import lru_cache

from app.core.config import get_settings
from app.providers.base import ChatModel
from app.providers.openai_compatible import OpenAICompatibleModel

_override: ChatModel | None = None
_override_set = False


@lru_cache
def _configured() -> ChatModel | None:
    settings = get_settings()
    if not settings.ai_configured:
        return None
    assert settings.ai_model is not None
    return OpenAICompatibleModel(
        model=settings.ai_model,
        api_key=settings.ai_api_key,
        base_url=settings.ai_provider_base_url,
        timeout_seconds=settings.ai_timeout_seconds,
        max_retries=settings.ai_max_retries,
        reasoning_effort=settings.ai_reasoning_effort,
        max_output_tokens=settings.ai_max_output_tokens,
    )


def get_provider() -> ChatModel | None:
    if _override_set:
        return _override
    return _configured()


def set_provider_override(provider: ChatModel | None, enabled: bool = True) -> None:
    """Test hook: force a model (or None) regardless of environment configuration."""
    global _override, _override_set
    _override = provider
    _override_set = enabled
