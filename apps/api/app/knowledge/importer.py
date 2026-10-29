"""Idempotent import of validated seed knowledge into the kb_* tables."""

import hashlib
import json

from sqlalchemy import delete, select
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
from app.knowledge.seed_loader import SeedBundle
from app.knowledge.text import normalize


def bundle_fingerprint(bundle: SeedBundle) -> str:
    payload = json.dumps(bundle.model_dump(mode="json", by_alias=True), sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def _norm_terms(values: list[str]) -> list[str]:
    return [normalize(v) for v in values if normalize(v)]


def import_bundle(db: Session, bundle: SeedBundle) -> dict[str, int | str | bool]:
    fingerprint = bundle_fingerprint(bundle)
    current = db.scalar(select(KbMeta.value).where(KbMeta.key == "import_id"))
    if current == fingerprint:
        return {"changed": False, "import_id": fingerprint, "services": len(bundle.services)}

    for model in (KbDependency, KbRequirement, KbService, KbLifeEvent, KbGlossaryTerm, KbSource):
        db.execute(delete(model))

    for source in bundle.sources:
        db.add(
            KbSource(
                id=source.id,
                title_en=source.title.en,
                title_ar=source.title.ar,
                url=source.url,
                publisher_en=source.publisher.en,
                publisher_ar=source.publisher.ar,
                checked_at=source.checked_at,
                source_updated_at=source.source_updated_at,
                verification_status=source.verification_status,
                review_note=source.review_note,
            )
        )
    for event in bundle.life_events:
        db.add(
            KbLifeEvent(
                id=event.id,
                label_en=event.label.en,
                label_ar=event.label.ar,
                keywords={
                    loc: {normalize(k): w for k, w in terms.items()}
                    for loc, terms in event.keywords.items()
                },
                facets=[
                    {
                        "id": f.id,
                        "label": f.label.model_dump(),
                        "keywords": {loc: _norm_terms(v) for loc, v in f.keywords.items()},
                    }
                    for f in event.facets
                ],
                clarification_prompt_en=(
                    event.clarification.prompt.en if event.clarification else None
                ),
                clarification_prompt_ar=(
                    event.clarification.prompt.ar if event.clarification else None
                ),
                examples={loc: list(v) for loc, v in event.examples.items()},
            )
        )
    db.flush()
    for position, service in enumerate(bundle.services):
        db.add(
            KbService(
                id=service.id,
                position=position,
                life_event_ids=service.life_event_ids,
                facets=service.facets,
                title_en=service.title.en,
                title_ar=service.title.ar,
                summary_en=service.summary.en,
                summary_ar=service.summary.ar,
                entity_en=service.entity.en,
                entity_ar=service.entity.ar,
                jurisdiction_en=service.jurisdiction.en,
                jurisdiction_ar=service.jurisdiction.ar,
                authority_en=service.authority.en,
                authority_ar=service.authority.ar,
                fee_text_en=service.fee_text.en if service.fee_text else None,
                fee_text_ar=service.fee_text.ar if service.fee_text else None,
                processing_time_text_en=(
                    service.processing_time_text.en if service.processing_time_text else None
                ),
                processing_time_text_ar=(
                    service.processing_time_text.ar if service.processing_time_text else None
                ),
                official_url=service.official_url,
                support_url=service.support_url,
                verification_status=service.verification_status,
                keywords={loc: _norm_terms(v) for loc, v in service.keywords.items()},
                profile_hints=[
                    {
                        "field": h.field,
                        "values": {k: v.model_dump() for k, v in h.values.items()},
                        "source_ids": h.source_ids,
                    }
                    for h in service.profile_hints
                ],
                source_ids=service.source_ids,
                review_note=service.review_note,
            )
        )
        db.flush()
        for rpos, req in enumerate(service.requirements):
            db.add(
                KbRequirement(
                    id=req.id,
                    service_id=service.id,
                    kind=req.kind,
                    position=rpos,
                    text_en=req.text.en,
                    text_ar=req.text.ar,
                    source_ids=req.source_ids,
                    rule={"field": req.rule.field, "in": req.rule.in_} if req.rule else None,
                )
            )
    db.flush()
    for dep in bundle.dependencies:
        db.add(
            KbDependency(
                id=dep.id,
                from_service_id=dep.from_,
                to_service_id=dep.to,
                kind=dep.kind,
                explanation_en=dep.explanation.en,
                explanation_ar=dep.explanation.ar,
                source_ids=dep.source_ids,
                condition=(
                    {"field": dep.condition.field, "in": dep.condition.in_}
                    if dep.condition
                    else None
                ),
            )
        )
    for term in bundle.glossary:
        db.add(
            KbGlossaryTerm(
                id=term.id,
                terms={loc: _norm_terms(v) for loc, v in term.terms.items()},
                definition_en=term.definition.en,
                definition_ar=term.definition.ar,
                source_ids=term.source_ids,
            )
        )
    meta = db.get(KbMeta, "import_id")
    if meta is None:
        db.add(KbMeta(key="import_id", value=fingerprint))
    else:
        meta.value = fingerprint
    db.commit()
    return {"changed": True, "import_id": fingerprint, "services": len(bundle.services)}
