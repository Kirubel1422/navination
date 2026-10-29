"""Runtime configuration loaded from environment variables (see .env.example)."""

from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

API_ROOT = Path(__file__).resolve().parents[2]
CONTRACT_VERSION = "1.1.0"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=API_ROOT / ".env", extra="ignore")

    app_env: Literal["development", "test", "production"] = "development"
    database_url: str = f"sqlite:///{API_ROOT / 'data' / 'navination.db'}"
    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:3000", "http://127.0.0.1:3000"]
    )
    session_ttl_hours: float = 24.0
    log_level: str = "INFO"

    # AI agent. Every discovery, plan, assessment and coach answer is produced by an agent on an
    # OpenAI-compatible Chat Completions endpoint (OpenAI, Azure OpenAI, vLLM, Ollama, ...).
    # There is no rule-based fallback: without a configured model those requests return 503.
    ai_provider: Literal["openai_compatible", "disabled"] = "openai_compatible"
    ai_model: str | None = None
    ai_api_key: str | None = None
    ai_provider_base_url: str | None = None  # default: https://api.openai.com/v1
    ai_timeout_seconds: float = 60.0  # per model call
    ai_max_retries: int = 1  # the SDK honours Retry-After on 429, which paces rate-limited tiers
    # Optional, provider-specific knobs (sent only when set): reasoning effort for reasoning models
    # such as gpt-oss, and a cap on output tokens per call.
    ai_reasoning_effort: Literal["low", "medium", "high"] | None = None
    # How agents deliver their final answer: "json_schema" (strict structured output in a separate
    # answer call; most reliable) or "tool" (a submit_* function call, for servers without
    # JSON-schema support). In tool mode schemas use $ref unless AI_INLINE_SCHEMAS=true.
    ai_structured_output: Literal["json_schema", "tool"] = "json_schema"
    ai_inline_schemas: bool = False
    # Research phase before answering: "auto" = the coach always researches; search and planning
    # research only when web search is configured (their context already holds the catalog).
    agent_research: Literal["auto", "always", "never"] = "auto"
    ai_max_output_tokens: int | None = None
    agent_max_steps: int = 10  # model calls per agent run
    agent_deadline_seconds: float = 150.0  # wall clock per agent run

    # Official-web tools for the agent. Pages are only fetched from these domains (and their
    # subdomains) over HTTPS. Web search additionally needs a search API key.
    official_domains: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: [
            "u.ae",
            "gov.ae",
            "tamm.abudhabi",
            "uaepass.ae",
            "bayanat.ae",
            "ajman.ae",
        ]
    )
    web_fetch_enabled: bool = True
    web_fetch_timeout_seconds: float = 10.0
    web_search_provider: Literal["none", "tavily", "brave"] = "none"
    web_search_api_key: str | None = None
    # Open-data APIs for the discovery agent (no keys needed): bayanat.ae (federal) and
    # data.ajman.ae (Ajman). Their dataset pages become citable once the agent opens them.
    bayanat_enabled: bool = True
    ajman_data_enabled: bool = True
    # Nearby service centres (OpenStreetMap via the public Photon geocoder; no key needed).
    places_enabled: bool = True
    # Open data layer: mirror the Bayanat/Ajman catalogues and refresh the curated datasets in the
    # background when older than this (bundled copies serve until then).
    open_data_sync: bool = True
    open_data_max_age_hours: float = 24.0

    # Request limits
    max_request_bytes: int = 32_768
    session_create_limit_per_minute: int = 20
    coach_limit_per_minute: int = 12
    discover_limit_per_minute: int = 30
    plan_limit_per_minute: int = 10

    @field_validator("cors_origins", "official_domains", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @field_validator("database_url")
    @classmethod
    def _anchor_relative_sqlite(cls, value: str) -> str:
        """sqlite:///./data/x.db is resolved against apps/api, whatever the working directory."""
        prefix = "sqlite:///./"
        if value.startswith(prefix):
            return f"sqlite:///{(API_ROOT / value[len(prefix) :]).resolve()}"
        return value

    @field_validator(
        "ai_api_key",
        "ai_provider_base_url",
        "ai_model",
        "web_search_api_key",
        "ai_reasoning_effort",
        "ai_max_output_tokens",
        mode="before",
    )
    @classmethod
    def _blank_is_none(cls, value: object) -> object:
        return None if isinstance(value, str) and not value.strip() else value

    @property
    def ai_configured(self) -> bool:
        """A model name is required; a key is required unless a custom (e.g. local) base URL is set."""
        if self.ai_provider != "openai_compatible" or not self.ai_model:
            return False
        return bool(self.ai_api_key) or bool(self.ai_provider_base_url)

    @property
    def web_search_configured(self) -> bool:
        return self.web_search_provider != "none" and bool(self.web_search_api_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()
