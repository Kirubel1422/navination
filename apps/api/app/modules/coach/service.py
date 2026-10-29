"""Agentic step coach: researches with tools and answers with validated citations and actions."""

import hashlib
import re
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session as DbSession

from app.agent import prompts
from app.agent.drafts import CoachDraft
from app.agent.places import get_places
from app.agent.reach import check_reach, store_reach
from app.agent.runner import execute, trace_json
from app.agent.runtime import AgentContext, FinishTool, Tool, ToolError
from app.agent.tools import (
    catalog_tools,
    contacts_tool,
    glossary_tool,
    open_data_facts,
    open_data_tool,
    places_tool,
    web_tools,
)
from app.agent.web import get_official_web, host_of
from app.core.config import get_settings
from app.core.errors import AppError, not_found
from app.core.timeutil import iso, utcnow
from app.db.models import CoachMessage as MessageRow
from app.db.models import GuestSession
from app.db.models import Journey as JourneyRow
from app.knowledge.repository import Knowledge
from app.modules.coach import schemas
from app.modules.discovery.schemas import AgentStep
from app.modules.journeys.service import require_fresh
from app.modules.services import registry
from app.modules.services.schemas import Source
from app.modules.sessions.service import new_id, profile_of

URL_PATTERN = re.compile(r"https?://[^\s)\]>\"']+", re.IGNORECASE)
HISTORY_LIMIT = 8


def fingerprint(body: schemas.CoachRequest) -> str:
    return hashlib.sha256(f"{body.step_id or ''}\x00{body.message}".encode()).hexdigest()


def _web_source(citation: dict[str, Any]) -> Source:
    return Source(
        id=citation["id"],
        title=citation["title"],
        url=citation["url"],
        publisher=citation["publisher"],
        checked_at=citation["checked_at"],
        source_updated_at=None,
        verification_status="needs_review",
    )


def message_schema(
    db: DbSession, kb: Knowledge, session_id: str, row: MessageRow, locale: str
) -> schemas.CoachMessage:
    citations: list[Source] = []
    for ref in row.citation_source_ids:
        if ref in kb.sources:
            s = kb.sources[ref]
            citations.append(
                Source(
                    id=s.id,
                    title=s.title[locale],
                    url=s.url,
                    publisher=s.publisher[locale],
                    checked_at=s.checked_at,
                    source_updated_at=s.source_updated_at,
                    verification_status=s.verification_status,  # type: ignore[arg-type]
                )
            )
    citations += [_web_source(c) for c in row.web_citations]
    return schemas.CoachMessage(
        id=row.id,
        role=row.role,  # type: ignore[arg-type]
        content=row.content,
        step_id=row.step_id,
        citations=citations,
        reach=registry.reach_schema(row.reach, locale),
        created_at=row.created_at,
    )


def list_messages(
    db: DbSession, kb: Knowledge, journey: JourneyRow, locale: str
) -> list[schemas.CoachMessage]:
    return [message_schema(db, kb, journey.session_id, row, locale) for row in journey.messages]


def _step_detail(db: DbSession, kb: Knowledge, journey: JourneyRow, step_id: str) -> dict[str, Any]:
    step = next((s for s in journey.steps if s.id == step_id), None)
    if step is None:
        raise ToolError(f"Unknown step_id {step_id!r}. Use ids from STEPS.")
    record = registry.resolve(db, kb, journey.session_id, step.service_id)
    deps = [
        d for d in (journey.plan or {}).get("dependencies", []) if step.key in (d["from"], d["to"])
    ]
    by_key = {s.key: s for s in journey.steps}
    return {
        "step_id": step.id,
        "title": step.title.get("en"),
        "instructions": step.instructions.get("en"),
        "user_reported_progress": step.progress,
        "checklist": [
            {
                "text": item["text"]["en"],
                "user_status": step.document_progress.get(item["id"], "unknown"),
                "source_ids": item["source_ids"],
                "ai_generated": item["ai_generated"],
            }
            for item in step.checklist
        ],
        "dependencies": [
            {
                "kind": d["kind"],
                "before_step_id": by_key[d["from"]].id if d["from"] in by_key else None,
                "after_step_id": by_key[d["to"]].id if d["to"] in by_key else None,
                "explanation": d["explanation"]["en"],
            }
            for d in deps
        ],
        "service": None
        if record is None
        else {
            "service_id": record.id,
            "origin": record.origin,
            "title": record.title["en"],
            "summary": record.summary["en"],
            "entity": record.entity["en"],
            "deciding_authority": record.authority["en"],
            "verification_status": record.verification_status,
            "criteria": [c["text"]["en"] for c in record.criteria],
            "documents": [d["text"]["en"] for d in record.documents],
            "fee_text": record.fee_text["en"] if record.fee_text else None,
            "processing_time_text": record.processing_time_text["en"]
            if record.processing_time_text
            else None,
            "has_official_url": bool(record.official_url),
            "has_support_url": bool(record.support_url),
            "sources": [
                {"source_id": s.id, "title": s.title["en"], "url": s.url} for s in record.sources
            ],
        },
    }


def _plan_sources(db: DbSession, kb: Knowledge, journey: JourneyRow) -> dict[str, dict[str, Any]]:
    """Sources the coach may cite without fetching: every source of every service in the plan."""
    out: dict[str, dict[str, Any]] = {}
    for step in journey.steps:
        record = registry.resolve(db, kb, journey.session_id, step.service_id)
        for source in record.sources if record else []:
            out[source.id] = {
                "catalog": source.id in kb.sources,
                "id": source.id,
                "url": source.url,
                "title": source.title["en"],
                "publisher": source.publisher["en"],
                "checked_at": iso(source.checked_at),
            }
    return out


def coach_turn(
    db: DbSession,
    session: GuestSession,
    kb: Knowledge,
    journey: JourneyRow,
    body: schemas.CoachRequest,
) -> schemas.CoachTurn:
    existing = db.scalar(
        select(MessageRow).where(
            MessageRow.journey_id == journey.id,
            MessageRow.client_message_id == body.client_message_id,
        )
    )
    if existing is not None:
        if existing.payload_fingerprint == fingerprint(body) and existing.turn:
            return schemas.CoachTurn.model_validate(existing.turn)
        raise AppError(
            409,
            "MESSAGE_ID_CONFLICT",
            "This client_message_id was already used for a different message.",
        )
    require_fresh(journey, session)

    locale = session.locale
    if body.step_id is not None and not any(s.id == body.step_id for s in journey.steps):
        raise not_found("This step was not found in the plan.")
    current_id = body.step_id or next(
        (s.id for s in journey.steps if s.progress != "completed"), None
    )

    settings = get_settings()
    ctx = AgentContext(
        location=(body.location.lat, body.location.lng) if body.location else None,
        emirate=profile_of(session).get("emirate"),
    )
    web = get_official_web(settings)

    def get_step(args: dict[str, Any]) -> Any:
        step_id = str(args.get("step_id", ""))
        ctx.record("get_step", step_id)
        return _step_detail(db, kb, journey, step_id)

    plan_sources = _plan_sources(db, kb, journey)
    payload = {
        "LOCALE": locale,
        "PROFILE": profile_of(session),
        "PLAN_TITLE": (journey.plan or {}).get("title", {}).get("en"),
        "STEPS": [
            {
                "step_id": s.id,
                "title": s.title.get("en"),
                "stage": s.order_group,
                "user_reported_progress": s.progress,
            }
            for s in journey.steps
        ],
        "CURRENT_STEP": _step_detail(db, kb, journey, current_id) if current_id else None,
        "CITABLE_PLAN_SOURCES": [
            {"source_id": k, "title": v["title"]} for k, v in plan_sources.items()
        ],
        "RECENT_MESSAGES": [
            {"role": m.role, "content": m.content[:1500]} for m in journey.messages[-HISTORY_LIMIT:]
        ],
        "QUESTION": body.message,
        "WEB_TOOLS": {
            "fetch": web.fetch_enabled,
            "search": web.search_available,
            "contacts": web.fetch_enabled,
            "service_centers": settings.places_enabled,
        },
        "LOCATION": {"shared": ctx.location is not None, "emirate": ctx.emirate},
        "OPEN_DATA": open_data_facts(
            list(dict.fromkeys(s.service_id for s in journey.steps)), profile_of(session), ctx
        ),
    }
    get_step_tool = Tool(
        "get_step",
        "Full details of one step in this plan: instructions, checklist with the person's status, "
        "dependencies and the service record with its sources.",
        {
            "type": "object",
            "properties": {"step_id": {"type": "string"}},
            "required": ["step_id"],
            "additionalProperties": False,
        },
        get_step,
    )

    def check(draft: CoachDraft) -> list[str]:
        problems = []
        for ref in draft.citation_refs:
            if ref not in plan_sources and ref not in kb.sources and ref not in ctx.read_pages:
                problems.append(
                    f"citation {ref!r} is not a plan source id, catalog source id or a page you fetched."
                )
        return problems + check_reach(draft.reach, ctx, "reach")

    draft = execute(
        system=prompts.COACH,
        payload=payload,
        tools=[
            get_step_tool,
            glossary_tool(kb, ctx),
            *catalog_tools(kb, ctx),
            *web_tools(web, ctx),
            open_data_tool(profile_of(session), ctx),
            *([contacts_tool(web, ctx)] if web.fetch_enabled else []),
            *(
                [places_tool(get_places(settings.web_fetch_timeout_seconds), ctx)]
                if settings.places_enabled
                else []
            ),
        ],
        finish=FinishTool("submit_answer", "Submit the answer for the person.", CoachDraft, check),
        ctx=ctx,
    )

    catalog_ids: list[str] = []
    web_citations: list[dict[str, Any]] = []
    for ref in dict.fromkeys(draft.citation_refs):
        if ref in kb.sources:
            catalog_ids.append(ref)
        elif ref in plan_sources:
            src = plan_sources[ref]
            if src["catalog"]:
                catalog_ids.append(ref)
            else:
                web_citations.append(
                    {k: src[k] for k in ("id", "url", "title", "publisher", "checked_at")}
                )
        elif ref in ctx.read_pages:
            page = ctx.read_pages[ref]
            web_citations.append(
                {
                    "id": registry.web_source_id(page.url),
                    "url": page.url,
                    "title": page.title,
                    "publisher": host_of(page.url),
                    "checked_at": iso(page.fetched_at),
                }
            )
    grounding = draft.grounding_status
    if grounding == "grounded" and not (catalog_ids or web_citations):
        grounding = "insufficient_evidence"

    # Only official URLs the system knows (records or pages read in this run) may appear in text.
    known_urls = {c["url"] for c in web_citations} | {
        v["url"] for v in plan_sources.values() if v["url"]
    }
    known_urls |= {s.url for s in kb.sources.values() if s.url} | set(ctx.read_pages)
    for step in journey.steps:
        record = registry.resolve(db, kb, journey.session_id, step.service_id)
        if record:
            known_urls |= {u for u in (record.official_url, record.support_url) if u}
    text = URL_PATTERN.sub(
        lambda m: m.group(0) if m.group(0) in known_urls else "[link removed]", draft.answer
    )

    steps_by_id = {s.id: s for s in journey.steps}
    actions: list[dict[str, str | None]] = []
    for action in draft.suggested_actions:
        step = steps_by_id.get(action.step_id or "")
        if step is None:
            continue
        record = registry.resolve(db, kb, journey.session_id, step.service_id)
        if record is None:
            continue
        if action.type == "open_official" and not record.official_url:
            continue
        if action.type == "open_support" and not record.support_url:
            continue
        entry = {
            "type": action.type,
            "step_id": step.id,
            "service_id": None if action.type == "view_step" else record.id,
        }
        if entry not in actions:
            actions.append(entry)

    now = utcnow()
    sequence = (
        db.scalar(select(func.max(MessageRow.sequence)).where(MessageRow.journey_id == journey.id))
        or 0
    )
    user_row = MessageRow(
        id=new_id("msg"),
        journey_id=journey.id,
        sequence=sequence + 1,
        role="user",
        content=body.message,
        step_id=current_id,
        citation_source_ids=[],
        web_citations=[],
        created_at=now,
        client_message_id=body.client_message_id,
        payload_fingerprint=fingerprint(body),
    )
    assistant_row = MessageRow(
        id=new_id("msg"),
        journey_id=journey.id,
        sequence=sequence + 2,
        role="assistant",
        content=text,
        step_id=current_id,
        citation_source_ids=catalog_ids,
        web_citations=web_citations,
        reach=store_reach(draft.reach, ctx),
        created_at=now,
    )
    turn = schemas.CoachTurn(
        user_message=message_schema(db, kb, session.id, user_row, locale),
        assistant_message=message_schema(db, kb, session.id, assistant_row, locale),
        mode="ai",
        grounding_status=grounding,  # type: ignore[arg-type]
        suggested_actions=[schemas.SuggestedAction(**a) for a in actions],  # type: ignore[arg-type]
        notices=[],
        agent_steps=[AgentStep(**s) for s in trace_json(ctx)],
    )
    user_row.turn = turn.model_dump(mode="json")
    db.add_all([user_row, assistant_row])
    db.commit()
    return turn
