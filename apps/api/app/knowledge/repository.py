"""Read-only, cached snapshot of the imported knowledge base.

The snapshot is rebuilt whenever the import fingerprint in kb_meta changes, so a re-seed is
picked up without restarting the API. Ordinary requests never contact external sites.
"""

import threading
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    KbDependency,
    KbGlossaryTerm,
    KbLifeEvent,
    KbMeta,
    KbRequirement,
    KbService,
    KbSource,
)


@dataclass(frozen=True)
class Source:
    id: str
    title: dict[str, str]
    url: str | None
    publisher: dict[str, str]
    checked_at: datetime | None
    source_updated_at: date | None
    verification_status: str


@dataclass(frozen=True)
class Requirement:
    id: str
    kind: str
    text: dict[str, str]
    source_ids: list[str]
    rule: dict[str, Any] | None


@dataclass(frozen=True)
class Service:
    id: str
    position: int
    life_event_ids: list[str]
    facets: list[str]
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
    keywords: dict[str, list[str]]
    profile_hints: list[dict[str, Any]]
    source_ids: list[str]
    criteria: list[Requirement]
    documents: list[Requirement]


@dataclass(frozen=True)
class Dependency:
    id: str
    from_service_id: str
    to_service_id: str
    kind: str
    explanation: dict[str, str]
    source_ids: list[str]
    condition: dict[str, Any] | None


@dataclass(frozen=True)
class LifeEvent:
    id: str
    label: dict[str, str]
    keywords: dict[str, dict[str, float]]
    facets: list[dict[str, Any]]
    clarification_prompt: dict[str, str] | None
    examples: dict[str, list[str]]


@dataclass(frozen=True)
class GlossaryTerm:
    id: str
    terms: dict[str, list[str]]
    definition: dict[str, str]
    source_ids: list[str]


@dataclass
class Knowledge:
    import_id: str | None
    sources: dict[str, Source] = field(default_factory=dict)
    services: dict[str, Service] = field(default_factory=dict)
    life_events: dict[str, LifeEvent] = field(default_factory=dict)
    dependencies: list[Dependency] = field(default_factory=list)
    glossary: list[GlossaryTerm] = field(default_factory=list)

    def services_for(self, life_event_id: str, facet_id: str | None = None) -> list[Service]:
        result = [
            s
            for s in self.services.values()
            if life_event_id in s.life_event_ids
            and (facet_id is None or not s.facets or facet_id in s.facets)
        ]
        return sorted(result, key=lambda s: s.position)

    @property
    def status(self) -> str:
        if not self.services:
            return "empty"
        statuses = {s.verification_status for s in self.services.values()}
        if statuses == {"verified"}:
            return "verified"
        if statuses == {"demo"}:
            return "demo"
        return "mixed"


def _loc(row: Any, name: str) -> dict[str, str]:
    return {"en": getattr(row, f"{name}_en"), "ar": getattr(row, f"{name}_ar")}


def _opt_loc(row: Any, name: str) -> dict[str, str] | None:
    en = getattr(row, f"{name}_en")
    return None if en is None else {"en": en, "ar": getattr(row, f"{name}_ar")}


def _build(db: Session, import_id: str | None) -> Knowledge:
    kb = Knowledge(import_id=import_id)
    for s in db.scalars(select(KbSource)):
        kb.sources[s.id] = Source(
            id=s.id,
            title=_loc(s, "title"),
            url=s.url,
            publisher=_loc(s, "publisher"),
            checked_at=s.checked_at,
            source_updated_at=s.source_updated_at,
            verification_status=s.verification_status,
        )
    reqs: dict[str, list[KbRequirement]] = {}
    for r in db.scalars(select(KbRequirement).order_by(KbRequirement.position)):
        reqs.setdefault(r.service_id, []).append(r)
    for svc in db.scalars(select(KbService).order_by(KbService.position)):
        converted = [
            Requirement(r.id, r.kind, _loc(r, "text"), list(r.source_ids), r.rule)
            for r in reqs.get(svc.id, [])
        ]
        kb.services[svc.id] = Service(
            id=svc.id,
            position=svc.position,
            life_event_ids=list(svc.life_event_ids),
            facets=list(svc.facets),
            title=_loc(svc, "title"),
            summary=_loc(svc, "summary"),
            entity=_loc(svc, "entity"),
            jurisdiction=_loc(svc, "jurisdiction"),
            authority=_loc(svc, "authority"),
            fee_text=_opt_loc(svc, "fee_text"),
            processing_time_text=_opt_loc(svc, "processing_time_text"),
            official_url=svc.official_url,
            support_url=svc.support_url,
            verification_status=svc.verification_status,
            keywords=dict(svc.keywords),
            profile_hints=list(svc.profile_hints),
            source_ids=list(svc.source_ids),
            criteria=[r for r in converted if r.kind == "criterion"],
            documents=[r for r in converted if r.kind == "document"],
        )
    for e in db.scalars(select(KbLifeEvent)):
        prompt = _opt_loc(e, "clarification_prompt")
        kb.life_events[e.id] = LifeEvent(
            id=e.id,
            label=_loc(e, "label"),
            keywords=dict(e.keywords),
            facets=list(e.facets),
            clarification_prompt=prompt,
            examples=dict(e.examples),
        )
    for d in db.scalars(select(KbDependency).order_by(KbDependency.id)):
        kb.dependencies.append(
            Dependency(
                id=d.id,
                from_service_id=d.from_service_id,
                to_service_id=d.to_service_id,
                kind=d.kind,
                explanation=_loc(d, "explanation"),
                source_ids=list(d.source_ids),
                condition=d.condition,
            )
        )
    for g in db.scalars(select(KbGlossaryTerm).order_by(KbGlossaryTerm.id)):
        kb.glossary.append(
            GlossaryTerm(
                id=g.id,
                terms=dict(g.terms),
                definition=_loc(g, "definition"),
                source_ids=list(g.source_ids),
            )
        )
    return kb


_cache: dict[str, Knowledge] = {}
_lock = threading.Lock()


def get_knowledge(db: Session) -> Knowledge:
    import_id = db.scalar(select(KbMeta.value).where(KbMeta.key == "import_id"))
    key = import_id or "__empty__"
    with _lock:
        cached = _cache.get(key)
    if cached is not None:
        return cached
    kb = _build(db, import_id)
    with _lock:
        _cache.clear()
        _cache[key] = kb
    return kb
