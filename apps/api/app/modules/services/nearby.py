"""Where and how to get a service done: nearby centres and the entity's published phone numbers.

An agent picks the right kind of centre for the service, searches near the person (their shared
location, or their emirate), and reads the entity's contact page. Centres must come from the
places tool and phone numbers from pages it read; the location is used for this request only.
"""

from typing import Any

from sqlalchemy.orm import Session as DbSession

from app.agent import prompts
from app.agent.drafts import NearbyDraft
from app.agent.places import get_places
from app.agent.reach import check_reach, store_reach
from app.agent.runner import execute
from app.agent.runtime import AgentContext, FinishTool
from app.agent.tools import catalog_tools, contacts_tool, places_tool, web_tools
from app.agent.web import get_official_web
from app.core.config import get_settings
from app.core.errors import AppError
from app.db.models import GuestSession
from app.knowledge.repository import Knowledge
from app.modules.services import registry, schemas
from app.modules.sessions.service import profile_of


def nearby(
    db: DbSession,
    session: GuestSession,
    kb: Knowledge,
    record: registry.ServiceRecord,
    body: schemas.NearbyRequest,
) -> schemas.Nearby:
    settings = get_settings()
    web = get_official_web(settings)
    if not settings.places_enabled and not web.fetch_enabled:
        raise AppError(
            503, "SERVICE_UNAVAILABLE", "Finding centres and contacts is turned off on this server."
        )
    profile = profile_of(session)
    ctx = AgentContext(
        location=(body.location.lat, body.location.lng) if body.location else None,
        emirate=profile.get("emirate"),
    )
    service: dict[str, Any] = {
        "service_id": record.id,
        "title": record.title["en"],
        "summary": record.summary["en"],
        "entity": record.entity["en"],
        "jurisdiction": record.jurisdiction["en"],
        "official_url": record.official_url,
        "support_url": record.support_url,
    }
    tools = [*catalog_tools(kb, ctx), *web_tools(web, ctx)]
    if web.fetch_enabled:
        tools.append(contacts_tool(web, ctx))
    if settings.places_enabled:
        tools.append(places_tool(get_places(settings.web_fetch_timeout_seconds), ctx))
    draft = execute(
        system=prompts.NEARBY,
        payload={
            "SERVICE": service,
            "LOCATION": {"shared": ctx.location is not None},
            "EMIRATE": ctx.emirate,
            "REQUEST": body.request,
            "LOCALE": session.locale,
        },
        tools=tools,
        finish=FinishTool(
            "submit_nearby",
            "Submit the reply, centres and contacts.",
            NearbyDraft,
            lambda d: check_reach(d.reach, ctx, "reach"),
        ),
        ctx=ctx,
        research=True,
    )
    stored = store_reach(draft.reach, ctx) or {"contacts": [], "centers": [], "map_query": None}
    reach = registry.reach_schema(stored, session.locale)
    assert reach is not None
    return schemas.Nearby(
        service_id=record.id,
        message=draft.message.en if session.locale == "en" else draft.message.ar,
        reach=reach,
    )
