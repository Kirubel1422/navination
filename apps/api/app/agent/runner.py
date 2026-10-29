"""Runs an agent with configured budgets and maps every failure to an honest 503."""

import json
import logging
from typing import Any

from pydantic import BaseModel

from app.agent.runtime import AgentContext, AgentError, FinishTool, Tool, run_agent
from app.core.config import get_settings
from app.core.errors import AppError
from app.providers.base import ChatModel
from app.providers.registry import get_provider

logger = logging.getLogger("navination.agent")


def ai_unavailable(reason: str) -> AppError:
    return AppError(
        503,
        "SERVICE_UNAVAILABLE",
        "The AI assistant is unavailable right now. Nothing was changed; please try again shortly.",
        [{"field": None, "message": reason}],
    )


def require_model() -> ChatModel:
    model = get_provider()
    if model is None:
        raise ai_unavailable("No AI model is configured on the server (AI_MODEL / AI_API_KEY).")
    return model


def execute[T: BaseModel](
    *,
    system: str,
    payload: dict[str, Any],
    tools: list[Tool],
    finish: FinishTool[T],
    ctx: AgentContext,
    research: bool = True,
) -> T:
    model = require_model()
    settings = get_settings()
    try:
        result = run_agent(
            model,
            system=system,
            user=json.dumps(payload, ensure_ascii=False, default=str),
            tools=tools,
            finish=finish,
            max_steps=settings.agent_max_steps,
            deadline_seconds=settings.agent_deadline_seconds,
            inline_refs=settings.ai_inline_schemas,
            structured_output=settings.ai_structured_output,
            research={"always": True, "never": False}.get(settings.agent_research, research),
        )
    except AgentError as exc:
        logger.warning("agent %s failed: %s (steps=%d)", finish.name, exc, len(ctx.trace))
        raise ai_unavailable(f"The AI agent could not complete the task ({exc}).") from exc
    return result


def trace_json(ctx: AgentContext) -> list[dict[str, str]]:
    return [{"tool": step.tool, "detail": step.detail} for step in ctx.trace]
