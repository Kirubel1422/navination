"""Verified handoffs. Destinations come only from service records, never from model output or
the browser: reviewed catalog records must be verified, and AI-found records may only point to
official-domain pages the agent actually read."""

from sqlalchemy.orm import Session as DbSession

from app.agent.web import is_official_url
from app.core.config import get_settings
from app.core.errors import AppError, not_found
from app.core.i18n import t
from app.core.timeutil import utcnow
from app.db.models import GuestSession, Handoff
from app.db.models import Journey as JourneyRow
from app.knowledge.repository import Knowledge
from app.knowledge.seed_loader import DESTINATION_HOST_SUFFIXES
from app.modules.handoffs import schemas
from app.modules.journeys.service import require_fresh
from app.modules.services import registry
from app.modules.sessions.service import new_id


def _allowed(record: registry.ServiceRecord, url: str | None) -> bool:
    if not url:
        return False
    if record.origin == "catalog":
        return record.verification_status == "verified" and is_official_url(
            url, [s.lstrip(".") for s in DESTINATION_HOST_SUFFIXES]
        )
    return is_official_url(url, get_settings().official_domains)


def create_handoff(
    db: DbSession,
    session: GuestSession,
    kb: Knowledge,
    journey: JourneyRow,
    body: schemas.HandoffRequest,
) -> schemas.Handoff:
    require_fresh(journey, session)
    step = next((s for s in journey.steps if s.id == body.step_id), None)
    if step is None:
        raise not_found("This step was not found in the plan.")
    record = registry.resolve(db, kb, session.id, step.service_id)
    url = None
    if record is not None:
        url = record.official_url if body.kind == "official" else record.support_url
    if record is None or not _allowed(record, url):
        raise AppError(
            409,
            "HANDOFF_UNAVAILABLE",
            "We don't have a verified destination for this step. Contact the responsible entity directly.",
        )
    assert url is not None
    row = Handoff(
        id=new_id("hnd"),
        journey_id=journey.id,
        step_id=step.id,
        service_id=record.id,
        kind=body.kind,
        url=url,
        created_at=utcnow(),
    )
    db.add(row)
    db.commit()
    key = "handoff_label_official" if body.kind == "official" else "handoff_label_support"
    return schemas.Handoff(
        id=row.id,
        kind=body.kind,
        service_id=record.id,
        url=url,
        label=t(session.locale, key, entity=record.entity[session.locale]),
        created_at=row.created_at,
    )
