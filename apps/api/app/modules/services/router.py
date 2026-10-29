from fastapi import APIRouter, Path

from app.core.config import get_settings
from app.core.errors import not_found
from app.core.ratelimit import rate_limiter
from app.core.schemas import error_responses
from app.knowledge.repository import get_knowledge
from app.modules.discovery.service import assess, latest_assessment
from app.modules.services import registry
from app.modules.services.nearby import nearby
from app.modules.services.schemas import Nearby, NearbyRequest, ServiceCard
from app.modules.sessions.deps import CurrentSession, Db
from app.modules.sessions.service import profile_of

router = APIRouter(tags=["services"])


@router.get(
    "/services/{service_id}", response_model=ServiceCard, responses=error_responses(401, 404, 503)
)
def get_service(
    session: CurrentSession, db: Db, service_id: str = Path(max_length=80)
) -> ServiceCard:
    kb = get_knowledge(db)
    record = registry.resolve(db, kb, session.id, service_id)
    if record is None:
        raise not_found("This service is not in NaviNation's catalog or your search results.")
    assessment, request = latest_assessment(db, session, record.id)
    if assessment is None:
        assessment = assess(db, session, kb, record, request)
    return registry.card(kb, record, assessment, session.locale, profile_of(session))


@router.post(
    "/services/{service_id}/nearby",
    response_model=Nearby,
    responses=error_responses(401, 404, 422, 429, 503),
    summary="Nearby centres and published phone numbers for a service",
)
def get_nearby(
    body: NearbyRequest, session: CurrentSession, db: Db, service_id: str = Path(max_length=80)
) -> Nearby:
    rate_limiter.check(f"nearby:{session.id}", get_settings().plan_limit_per_minute)
    kb = get_knowledge(db)
    record = registry.resolve(db, kb, session.id, service_id)
    if record is None:
        raise not_found("This service is not in NaviNation's catalog or your search results.")
    return nearby(db, session, kb, record, body)
