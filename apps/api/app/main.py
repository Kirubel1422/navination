"""NaviNation API application factory."""

import logging
from typing import Literal

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.agent.web import get_official_web
from app.core.config import CONTRACT_VERSION, get_settings
from app.core.errors import install_error_handlers
from app.core.middleware import RequestContextMiddleware
from app.core.schemas import ResponseModel
from app.db.session import get_sessionmaker
from app.knowledge.repository import get_knowledge
from app.modules.coach.router import router as coach_router
from app.modules.discovery.router import router as discovery_router
from app.modules.handoffs.router import router as handoffs_router
from app.modules.journeys.router import router as journeys_router
from app.modules.services.router import router as services_router
from app.modules.sessions.router import router as sessions_router
from app.providers.registry import get_provider


class Health(ResponseModel):
    status: Literal["ok", "degraded"]
    contract_version: str
    knowledge_status: Literal["verified", "mixed", "demo", "empty"]
    ai_available: bool
    web_search_available: bool


health_router = APIRouter(tags=["health"])


@health_router.get("/health", response_model=Health)
def health() -> Health:
    knowledge_status = "empty"
    ok = True
    try:
        with get_sessionmaker()() as db:
            db.execute(text("SELECT 1"))
            knowledge_status = get_knowledge(db).status
    except Exception:  # noqa: BLE001 - health must report, not raise
        ok = False
    ai_available = get_provider() is not None
    return Health(
        # Every product request needs the AI agent, so a missing model means degraded.
        status="ok" if ok and knowledge_status != "empty" and ai_available else "degraded",
        contract_version=CONTRACT_VERSION,
        knowledge_status=knowledge_status,  # type: ignore[arg-type]
        ai_available=ai_available,
        web_search_available=get_official_web(get_settings()).search_available,
    )


def create_app() -> FastAPI:
    settings = get_settings()
    logging.basicConfig(
        level=settings.log_level, format="%(asctime)s %(levelname)s %(name)s %(message)s"
    )
    app = FastAPI(
        title="NaviNation API",
        version=CONTRACT_VERSION,
        description=(
            "NaviNation guides citizens and residents from an everyday need to reviewed UAE "
            "government services. Guidance only: responsible entities make every decision."
        ),
        docs_url="/api/v1/docs",
        openapi_url="/api/v1/openapi.json",
        redoc_url=None,
    )
    install_error_handlers(app)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
        expose_headers=["X-Request-ID", "Retry-After"],
    )
    app.add_middleware(RequestContextMiddleware)
    api = APIRouter(prefix="/api/v1")
    for router in (
        health_router,
        sessions_router,
        discovery_router,
        services_router,
        journeys_router,
        coach_router,
        handoffs_router,
    ):
        api.include_router(router)
    app.include_router(api)
    app.openapi = lambda: _contract_openapi(app)  # type: ignore[method-assign]
    return app


def _contract_openapi(app: FastAPI) -> dict:
    """FastAPI's default 422 schema differs from runtime; document the real ErrorEnvelope."""
    if app.openapi_schema:
        return app.openapi_schema
    from fastapi.openapi.utils import get_openapi

    schema = get_openapi(
        title=app.title, version=app.version, description=app.description, routes=app.routes
    )
    envelope_ref = {"$ref": "#/components/schemas/ErrorEnvelope"}
    for path in schema["paths"].values():
        for operation in path.values():
            responses = operation.get("responses", {})
            if "422" in responses:
                responses["422"] = {
                    "description": "Validation error",
                    "content": {"application/json": {"schema": envelope_ref}},
                }
            responses.setdefault(
                "500",
                {
                    "description": "Unexpected error",
                    "content": {"application/json": {"schema": envelope_ref}},
                },
            )
    for name in ("HTTPValidationError", "ValidationError"):
        schema["components"]["schemas"].pop(name, None)
    schema["info"]["x-contract-version"] = CONTRACT_VERSION
    app.openapi_schema = schema
    return schema


app = create_app()
