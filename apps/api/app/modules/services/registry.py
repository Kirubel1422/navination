"""One view over reviewed catalog services and services the agent found on official websites.

Catalog records come from the reviewed knowledge base. AI-found records are stored per guest
session; their sources are only pages the agent actually fetched, and they are always reported as
`needs_review` with origin `ai_web`.
"""

import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session as DbSession

from app.agent.drafts import Assessment, WebServiceDraft
from app.agent.runtime import AgentContext
from app.core.i18n import t
from app.core.timeutil import iso, utcnow
from app.db.models import AiService
from app.knowledge.repository import Knowledge
from app.knowledge.repository import Service as CatalogService
from app.modules.services import schemas
from app.modules.services.evaluation import readiness_of


@dataclass
class SourceRecord:
    id: str
    title: dict[str, str]
    url: str | None
    publisher: dict[str, str]
    checked_at: datetime | None
    source_updated_at: Any
    verification_status: str


@dataclass
class ServiceRecord:
    id: str
    origin: str
    life_event_ids: list[str]
    title: dict[str, str]
    summary: dict[str, str]
    entity: dict[str, str]
    jurisdiction: dict[str, str]
    authority: dict[str, str]
    fee_text: dict[str, str] | None
    processing_time_text: dict[str, str] | None
    official_url: str | None
    support_url: str | None
    verification_status: str
    criteria: list[dict[str, Any]]
    documents: list[dict[str, Any]]
    sources: list[SourceRecord] = field(default_factory=list)

    @property
    def source_ids(self) -> set[str]:
        return {s.id for s in self.sources}

    def ref_to_source_id(self, ref: str) -> str | None:
        """Map an agent reference (source id or fetched URL) to one of this service's sources."""
        for source in self.sources:
            if ref == source.id or (source.url and ref.rstrip("/") == source.url.rstrip("/")):
                return source.id
        return None


def web_source_id(url: str) -> str:
    return "web-" + hashlib.sha1(url.encode()).hexdigest()[:12]


def from_catalog(kb: Knowledge, service: CatalogService) -> ServiceRecord:
    return ServiceRecord(
        id=service.id,
        origin="catalog",
        life_event_ids=list(service.life_event_ids),
        title=service.title,
        summary=service.summary,
        entity=service.entity,
        jurisdiction=service.jurisdiction,
        authority=service.authority,
        fee_text=service.fee_text,
        processing_time_text=service.processing_time_text,
        official_url=service.official_url,
        support_url=service.support_url,
        verification_status=service.verification_status,
        criteria=[
            {"id": c.id, "text": c.text, "source_ids": c.source_ids} for c in service.criteria
        ],
        documents=[
            {"id": d.id, "text": d.text, "source_ids": d.source_ids} for d in service.documents
        ],
        sources=[
            SourceRecord(
                id=s.id,
                title=s.title,
                url=s.url,
                publisher=s.publisher,
                checked_at=s.checked_at,
                source_updated_at=s.source_updated_at,
                verification_status=s.verification_status,
            )
            for s in (kb.sources[sid] for sid in service.source_ids)
        ],
    )


def from_ai(row: AiService) -> ServiceRecord:
    data = row.data
    return ServiceRecord(
        id=row.id,
        origin="ai_web",
        life_event_ids=list(data.get("life_event_ids", [])),
        title=data["title"],
        summary=data["summary"],
        entity=data["entity"],
        jurisdiction=data["jurisdiction"],
        authority=data["authority"],
        fee_text=data.get("fee_text"),
        processing_time_text=data.get("processing_time_text"),
        official_url=data.get("official_url"),
        support_url=data.get("support_url"),
        verification_status="needs_review",
        criteria=data.get("criteria", []),
        documents=data.get("documents", []),
        sources=[
            SourceRecord(
                id=s["id"],
                title={"en": s["title"], "ar": s["title"]},
                url=s["url"],
                publisher={"en": s["publisher"], "ar": s["publisher"]},
                checked_at=datetime.fromisoformat(s["checked_at"].replace("Z", "+00:00")),
                source_updated_at=None,
                verification_status="needs_review",
            )
            for s in data.get("sources", [])
        ],
    )


def resolve(db: DbSession, kb: Knowledge, session_id: str, service_id: str) -> ServiceRecord | None:
    if service_id in kb.services:
        return from_catalog(kb, kb.services[service_id])
    row = db.get(AiService, service_id)
    if row is None or row.session_id != session_id:
        return None
    return from_ai(row)


def check_web_draft(draft: WebServiceDraft, ctx: AgentContext, where: str) -> list[str]:
    """Provenance: every URL must be an official page the agent fetched in this run."""
    problems = []
    for url in draft.source_urls:
        if url not in ctx.read_pages:
            problems.append(f"{where}: source_urls must be pages you fetched; not fetched: {url}")
    for name in ("official_url", "support_url"):
        url = getattr(draft, name)
        if url and url not in ctx.read_pages:
            problems.append(f"{where}: {name} must be a page you fetched; not fetched: {url}")
    allowed = set(draft.source_urls)
    for item in [*draft.criteria, *draft.documents]:
        for ref in item.source_refs:
            if ref not in allowed:
                problems.append(f"{where}: item source_refs must be among source_urls: {ref}")
    return problems


def save_web_service(
    db: DbSession, session_id: str, draft: WebServiceDraft, ctx: AgentContext, topic_id: str | None
) -> ServiceRecord:
    def page(url: str) -> dict[str, Any]:
        source = ctx.read_pages[url]
        return {
            "id": web_source_id(source.url),
            "url": source.url,
            "title": source.title,
            "publisher": source.publisher,
            "checked_at": iso(source.fetched_at),
        }

    sources = {}
    for url in draft.source_urls:
        record = page(url)
        sources[record["id"]] = record
    url_to_id = {url: page(url)["id"] for url in draft.source_urls}

    def items(prefix: str, drafts: list) -> list[dict[str, Any]]:  # type: ignore[type-arg]
        return [
            {
                "id": f"{prefix}{index + 1}",
                "text": item.text.model_dump(),
                "source_ids": [url_to_id[r] for r in item.source_refs if r in url_to_id],
            }
            for index, item in enumerate(drafts)
        ]

    anchor = draft.official_url or draft.source_urls[0]
    service_id = "web-svc-" + hashlib.sha1(f"{session_id}|{anchor}".encode()).hexdigest()[:12]
    data = {
        "life_event_ids": [topic_id] if topic_id else [],
        "title": draft.title.model_dump(),
        "summary": draft.summary.model_dump(),
        "entity": draft.entity.model_dump(),
        "jurisdiction": draft.jurisdiction.model_dump(),
        "authority": draft.authority.model_dump(),
        "fee_text": draft.fee_text.model_dump() if draft.fee_text else None,
        "processing_time_text": (
            draft.processing_time_text.model_dump() if draft.processing_time_text else None
        ),
        "official_url": ctx.read_pages[draft.official_url].url if draft.official_url else None,
        "support_url": ctx.read_pages[draft.support_url].url if draft.support_url else None,
        "criteria": items(f"{service_id}.c", draft.criteria),
        "documents": items(f"{service_id}.d", draft.documents),
        "sources": list(sources.values()),
    }
    row = db.get(AiService, service_id)
    if row is None:
        row = AiService(id=service_id, session_id=session_id, data=data, created_at=utcnow())
        db.add(row)
    else:
        row.data = data
    db.flush()
    return from_ai(row)


def stored_assessment(
    record: ServiceRecord, draft: Assessment, profile: dict[str, Any]
) -> dict[str, Any]:
    """Keep the agent's judgement; drop citations that do not belong to this service and
    'missing' fields the person has already answered."""
    return {
        "relevance": draft.relevance,
        "reasons": [
            {
                "text": reason.text.model_dump(),
                "source_ids": sorted(
                    {sid for ref in reason.source_refs if (sid := record.ref_to_source_id(ref))}
                ),
            }
            for reason in draft.reasons
        ],
        "missing_profile_fields": [
            f for f in dict.fromkeys(draft.missing_profile_fields) if profile.get(f) is None
        ],
    }


def source_schema(source: SourceRecord, locale: str) -> schemas.Source:
    return schemas.Source(
        id=source.id,
        title=source.title[locale],
        url=source.url,
        publisher=source.publisher[locale],
        checked_at=source.checked_at,
        source_updated_at=source.source_updated_at,
        verification_status=source.verification_status,  # type: ignore[arg-type]
    )


def service_schema(record: ServiceRecord, locale: str) -> schemas.Service:
    def req(item: dict[str, Any]) -> schemas.Requirement:
        return schemas.Requirement(
            id=item["id"], text=item["text"][locale], source_ids=list(item["source_ids"])
        )

    return schemas.Service(
        id=record.id,
        life_event_ids=record.life_event_ids,
        title=record.title[locale],
        summary=record.summary[locale],
        entity=record.entity[locale],
        jurisdiction=record.jurisdiction[locale],
        eligibility_criteria=[req(c) for c in record.criteria],
        documents=[req(d) for d in record.documents],
        fee_text=record.fee_text[locale] if record.fee_text else None,
        processing_time_text=(
            record.processing_time_text[locale] if record.processing_time_text else None
        ),
        official_url=record.official_url,
        support_url=record.support_url,
        sources=[source_schema(s, locale) for s in record.sources],
        verification_status=record.verification_status,  # type: ignore[arg-type]
        origin=record.origin,  # type: ignore[arg-type]
    )


def reach_schema(stored: dict[str, Any] | None, locale: str) -> schemas.Reach | None:
    if not stored:
        return None

    def text(value: dict[str, str] | None) -> str | None:
        return (value.get(locale) or value.get("en")) if value else None

    return schemas.Reach(
        contacts=[
            schemas.Contact(
                label=text(c["label"]) or "",
                phone=c["phone"],
                tel=c["tel"],
                email=c.get("email"),
                hours=text(c.get("hours")),
                source_url=c["source"]["url"],
                source_title=c["source"]["title"],
            )
            for c in stored.get("contacts", [])
        ],
        centers=[
            schemas.Center(
                id=c["id"],
                name=c["name"],
                address=c.get("address"),
                lat=c["lat"],
                lng=c["lng"],
                note=text(c.get("note")),
            )
            for c in stored.get("centers", [])
        ],
        map_query=stored.get("map_query"),
    )


def card(
    kb: Knowledge,
    record: ServiceRecord,
    assessment: dict[str, Any],
    locale: str,
    profile: dict[str, Any],
) -> schemas.ServiceCard:
    reasons = [
        schemas.Reason(text=r["text"][locale], source_ids=list(r["source_ids"]))
        for r in assessment.get("reasons", [])
    ]
    if record.origin == "ai_web":
        reasons.append(
            schemas.Reason(text=t(locale, "reason_ai_web"), source_ids=sorted(record.source_ids))
        )
    elif record.verification_status == "needs_review":
        reasons.append(
            schemas.Reason(
                text=t(locale, "reason_needs_review"), source_ids=sorted(record.source_ids)
            )
        )
    readiness = readiness_of(kb, record.id, profile) if record.origin == "catalog" else "unknown"
    return schemas.ServiceCard(
        service=service_schema(record, locale),
        relevance=assessment.get("relevance", "more_information_needed"),
        reasons=reasons,
        missing_profile_fields=assessment.get("missing_profile_fields", []),
        readiness=readiness,  # type: ignore[arg-type]
        authority_notice=t(locale, "authority_notice", authority=record.authority[locale]),
        reach=reach_schema(assessment.get("reach"), locale),
    )
