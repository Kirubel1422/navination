"""Agentic discovery: an AI agent interprets the need, researches with tools, and ranks services
for this person. The backend validates every service ID, URL and citation the agent returns."""

import secrets
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from app.agent import prompts
from app.agent.ajman import get_ajman
from app.agent.bayanat import get_bayanat
from app.agent.drafts import Assessment, DiscoveryDraft
from app.agent.places import get_places
from app.agent.reach import check_reach, store_reach
from app.agent.runner import execute, trace_json
from app.agent.runtime import AgentContext, FinishTool
from app.agent.tools import (
    ajman_tools,
    bayanat_tools,
    catalog_tools,
    compact_catalog,
    compact_service,
    contacts_tool,
    places_tool,
    web_tools,
)
from app.agent.web import get_official_web, host_of
from app.core.config import get_settings
from app.core.errors import context_stale, not_found, validation_error
from app.core.i18n import t
from app.core.timeutil import iso, utcnow
from app.db.models import Discovery, GuestSession
from app.knowledge.repository import Knowledge
from app.modules.discovery import schemas
from app.modules.services import registry
from app.modules.sessions.service import new_id, profile_of


def _resolve_answer(
    db: DbSession, session: GuestSession, body: schemas.DiscoverRequest
) -> dict[str, Any]:
    answer = body.clarification_answer
    assert answer is not None
    previous = db.get(Discovery, answer.discovery_id)
    if previous is None or previous.session_id != session.id:
        raise not_found("This discovery was not found.")
    if previous.status != "needs_clarification" or not previous.clarification:
        raise validation_error(
            "This discovery does not need clarification.", "clarification_answer"
        )
    if previous.context_revision != session.context_revision:
        raise context_stale(
            "Your profile changed after this question was asked. Please search again."
        )
    if previous.clarification["id"] != answer.question_id:
        raise validation_error(
            "The question ID does not match.", "clarification_answer.question_id"
        )
    option = next(
        (o for o in previous.clarification["options"] if o["id"] == answer.option_id), None
    )
    if option is None:
        raise validation_error(
            "Choose one of the offered options.", "clarification_answer.option_id"
        )
    if previous.query != body.query:
        raise validation_error("Send the original query when answering a clarification.", "query")
    return {"question": previous.clarification["question"]["en"], "answer": option["label"]["en"]}


def _checker(kb: Knowledge, ctx: AgentContext, answered: bool):  # type: ignore[no-untyped-def]
    def check(draft: DiscoveryDraft) -> list[str]:
        problems: list[str] = []
        if draft.status == "ready" and not draft.results:
            problems.append("status=ready needs at least one result.")
        if draft.status == "needs_clarification":
            if draft.clarification is None:
                problems.append("status=needs_clarification needs a clarification.")
            if answered:
                problems.append(
                    "The person already answered a clarification; decide with that answer."
                )
        seen: set[str] = set()
        for index, result in enumerate(draft.results if draft.status == "ready" else []):
            where = f"results[{index}]"
            if result.kind == "catalog":
                if result.service_id not in kb.services:
                    problems.append(f"{where}: unknown catalog service_id {result.service_id!r}.")
                elif result.service_id in seen:
                    problems.append(f"{where}: duplicate service {result.service_id}.")
                seen.add(result.service_id or "")
            else:
                if result.web_service is None:
                    problems.append(f"{where}: kind=web requires web_service.")
                else:
                    problems += registry.check_web_draft(result.web_service, ctx, where)
            problems += check_reach(result.reach, ctx, f"{where}.reach")
        for ref in draft.answer_refs:
            if ref not in kb.sources and ref not in ctx.read_pages:
                problems.append(
                    f"answer_refs: {ref!r} is not a catalog source id or a page you read."
                )
        return problems

    return check


def discover(
    db: DbSession, session: GuestSession, kb: Knowledge, body: schemas.DiscoverRequest
) -> schemas.Discovery:
    clarification = _resolve_answer(db, session, body) if body.clarification_answer else None
    profile = profile_of(session)
    settings = get_settings()
    web = get_official_web(settings)
    ctx = AgentContext(
        location=(body.location.lat, body.location.lng) if body.location else None,
        emirate=profile.get("emirate"),
    )
    ctx.record("read_catalog", f"{len(kb.services)} reviewed services")
    payload = {
        "CATALOG": compact_catalog(kb),
        "REQUEST": body.query,
        "PROFILE": profile,
        "LOCALE": session.locale,
        "CLARIFICATION_ANSWERED": clarification,
        "WEB_TOOLS": {
            "fetch": web.fetch_enabled,
            "search": web.search_available,
            "bayanat": settings.bayanat_enabled,
            "ajman_data": settings.ajman_data_enabled,
            "contacts": web.fetch_enabled,
            "service_centers": settings.places_enabled,
        },
        "LOCATION": {"shared": ctx.location is not None, "emirate": ctx.emirate},
    }
    tools = catalog_tools(kb, ctx) + web_tools(web, ctx)
    if settings.bayanat_enabled:
        tools += bayanat_tools(get_bayanat(settings.web_fetch_timeout_seconds), ctx)
    if settings.ajman_data_enabled:
        tools += ajman_tools(get_ajman(settings.web_fetch_timeout_seconds), ctx)
    if web.fetch_enabled:
        tools.append(contacts_tool(web, ctx))
    if settings.places_enabled:
        tools.append(places_tool(get_places(settings.web_fetch_timeout_seconds), ctx))
    draft = execute(
        system=prompts.DISCOVERY,
        payload=payload,
        tools=tools,
        finish=FinishTool(
            "submit_discovery",
            "Submit the interpreted need and ranked results (or a clarification / no_match).",
            DiscoveryDraft,
            _checker(kb, ctx, answered=clarification is not None),
        ),
        ctx=ctx,
        # The catalog is already in context; research only pays off with a search tool.
        research=web.search_available or settings.bayanat_enabled or settings.ajman_data_enabled,
    )

    topic_id = draft.topic.id if draft.topic else None
    service_ids: list[str] = []
    assessments: dict[str, Any] = {}
    if draft.status == "ready":
        for result in draft.results:
            if result.kind == "catalog":
                record = registry.from_catalog(kb, kb.services[result.service_id or ""])
            else:
                assert result.web_service is not None
                record = registry.save_web_service(
                    db, session.id, result.web_service, ctx, topic_id
                )
            if record.id in assessments:
                continue
            service_ids.append(record.id)
            assessments[record.id] = registry.stored_assessment(record, result.assessment, profile)
            reach = store_reach(result.reach, ctx)
            if reach:
                assessments[record.id]["reach"] = reach

    row = Discovery(
        id=new_id("dis"),
        session_id=session.id,
        context_revision=session.context_revision,
        query=body.query,
        status=draft.status,
        life_event_id=topic_id if draft.status == "ready" else None,
        facet_id=None,
        clarification=(
            {
                "id": "q_" + secrets.token_hex(4),
                "question": draft.clarification.question.model_dump(),
                "options": [
                    {"id": o.id, "label": o.label.model_dump()} for o in draft.clarification.options
                ],
            }
            if draft.status == "needs_clarification" and draft.clarification
            else None
        ),
        service_ids=service_ids,
        mode="ai",
        created_at=utcnow(),
        interpreted_need=draft.interpreted_need.model_dump(),
        topic_label=draft.topic.label.model_dump() if draft.topic else None,
        notices=[n.model_dump() for n in draft.notices],
        assessments=assessments,
        agent_steps=trace_json(ctx),
        answer=_stored_answer(draft, kb, ctx) if draft.status == "ready" else None,
    )
    db.add(row)
    db.commit()
    return render(db, kb, session, row)


def _stored_answer(
    draft: DiscoveryDraft, kb: Knowledge, ctx: AgentContext
) -> dict[str, Any] | None:
    if draft.answer is None:
        return None
    sources: list[dict[str, Any]] = []
    for ref in dict.fromkeys(draft.answer_refs):
        if ref in kb.sources:
            sources.append({"catalog_id": ref})
        elif ref in ctx.read_pages:
            page = ctx.read_pages[ref]
            sources.append(
                {
                    "id": registry.web_source_id(page.url),
                    "url": page.url,
                    "title": page.title,
                    "publisher": host_of(page.url),
                    "checked_at": iso(page.fetched_at),
                }
            )
    return {"text": draft.answer.model_dump(), "sources": sources}


def _answer_sources(kb: Knowledge, answer: dict[str, Any], locale: str) -> list[schemas.Source]:
    out: list[schemas.Source] = []
    for item in answer.get("sources", []):
        if "catalog_id" in item:
            source = kb.sources.get(item["catalog_id"])
            if source is not None:
                out.append(
                    schemas.Source(
                        id=source.id,
                        title=source.title[locale],
                        url=source.url,
                        publisher=source.publisher[locale],
                        checked_at=source.checked_at,
                        source_updated_at=source.source_updated_at,
                        verification_status=source.verification_status,  # type: ignore[arg-type]
                    )
                )
        else:
            out.append(
                schemas.Source(
                    id=item["id"],
                    title=item["title"],
                    url=item["url"],
                    publisher=item["publisher"],
                    checked_at=item["checked_at"],
                    source_updated_at=None,
                    verification_status="needs_review",
                )
            )
    return out


def render(
    db: DbSession, kb: Knowledge, session: GuestSession, row: Discovery
) -> schemas.Discovery:
    locale = session.locale
    profile = profile_of(session)
    cards = []
    for service_id in row.service_ids:
        record = registry.resolve(db, kb, session.id, service_id)
        if record is not None:
            cards.append(
                registry.card(kb, record, row.assessments.get(service_id, {}), locale, profile)
            )
    notices: list[str] = []
    if row.status == "no_match":
        notices.append(t(locale, "notice_no_match"))
    notices += [n[locale] for n in row.notices]
    clarification = None
    if row.clarification:
        clarification = schemas.Clarification(
            id=row.clarification["id"],
            prompt=row.clarification["question"][locale],
            options=[
                schemas.ClarificationOption(id=o["id"], label=o["label"][locale])
                for o in row.clarification["options"]
            ],
        )
    return schemas.Discovery(
        id=row.id,
        context_revision=row.context_revision,
        query=row.query,
        interpreted_need=(row.interpreted_need or {}).get(locale, ""),
        answer=(row.answer or {}).get("text", {}).get(locale) if row.answer else None,
        answer_sources=_answer_sources(kb, row.answer, locale) if row.answer else [],
        life_event_id=row.life_event_id,
        status=row.status,  # type: ignore[arg-type]
        clarification=clarification,
        results=cards if row.status == "ready" else [],
        mode="ai",
        notices=notices,
        agent_steps=[schemas.AgentStep(**s) for s in row.agent_steps],
    )


def latest_assessment(
    db: DbSession, session: GuestSession, service_id: str
) -> tuple[dict[str, Any] | None, str | None]:
    """The most recent AI assessment of a service at the session's current profile revision."""
    rows = db.scalars(
        select(Discovery)
        .where(Discovery.session_id == session.id, Discovery.status == "ready")
        .order_by(Discovery.created_at.desc())
    )
    latest_query = None
    for row in rows:
        latest_query = latest_query or row.query
        if row.context_revision == session.context_revision and service_id in row.assessments:
            return row.assessments[service_id], row.query
    return None, latest_query


def assess(
    db: DbSession,
    session: GuestSession,
    kb: Knowledge,
    record: registry.ServiceRecord,
    request: str | None,
) -> dict[str, Any]:
    """Ask the agent how one service fits this person (used when no current assessment exists)."""
    profile = profile_of(session)
    ctx = AgentContext()
    service: dict[str, Any] = {"service_id": record.id, "origin": record.origin}
    if record.origin == "catalog":
        service.update(compact_service(kb, record.id, with_documents=True))
    else:
        service.update(
            title=record.title["en"],
            summary=record.summary["en"],
            criteria=[c["text"]["en"] for c in record.criteria],
            sources=[
                {"source_id": s.id, "url": s.url, "title": s.title["en"]} for s in record.sources
            ],
        )
    draft = execute(
        system=prompts.ASSESSMENT,
        payload={
            "SERVICE": service,
            "PROFILE": profile,
            "REQUEST": request,
            "LOCALE": session.locale,
        },
        tools=catalog_tools(kb, ctx),
        finish=FinishTool("submit_assessment", "Submit the assessment.", Assessment),
        ctx=ctx,
        research=False,
    )
    return registry.stored_assessment(record, draft, profile)
