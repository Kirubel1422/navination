from fastapi import APIRouter, Path, status

from app.core.config import get_settings
from app.core.ratelimit import rate_limiter
from app.core.schemas import error_responses
from app.knowledge.repository import get_knowledge
from app.modules.journeys import service
from app.modules.journeys.schemas import (
    CreateJourneyRequest,
    Journey,
    ReplanRequest,
    StepUpdateRequest,
)
from app.modules.sessions.deps import CurrentSession, Db

router = APIRouter(tags=["journeys"])
JourneyId = Path(max_length=80)


@router.post(
    "/journeys",
    status_code=status.HTTP_201_CREATED,
    response_model=Journey,
    responses=error_responses(401, 404, 409, 422, 429, 503),
)
def create_journey(body: CreateJourneyRequest, session: CurrentSession, db: Db) -> Journey:
    rate_limiter.check(f"plan:{session.id}", get_settings().plan_limit_per_minute)
    kb = get_knowledge(db)
    journey = service.create_journey(db, session, kb, body)
    return service.render_journey(kb, journey, session, db)


@router.get("/journeys/{journey_id}", response_model=Journey, responses=error_responses(401, 404))
def get_journey(session: CurrentSession, db: Db, journey_id: str = JourneyId) -> Journey:
    kb = get_knowledge(db)
    journey = service.get_owned_journey(db, session, journey_id)
    return service.render_journey(kb, journey, session, db)


@router.post(
    "/journeys/{journey_id}/replan",
    response_model=Journey,
    responses=error_responses(401, 404, 409, 422, 429, 503),
)
def replan(
    body: ReplanRequest, session: CurrentSession, db: Db, journey_id: str = JourneyId
) -> Journey:
    kb = get_knowledge(db)
    journey = service.get_owned_journey(db, session, journey_id)
    rate_limiter.check(f"plan:{session.id}", get_settings().plan_limit_per_minute)
    service.replan(db, session, kb, journey)
    return service.render_journey(kb, journey, session, db)


@router.patch(
    "/journeys/{journey_id}/steps/{step_id}",
    response_model=Journey,
    responses=error_responses(401, 404, 409, 422),
)
def update_step(
    body: StepUpdateRequest,
    session: CurrentSession,
    db: Db,
    journey_id: str = JourneyId,
    step_id: str = Path(max_length=80),
) -> Journey:
    kb = get_knowledge(db)
    journey = service.get_owned_journey(db, session, journey_id)
    service.update_step(db, session, journey, step_id, body)
    return service.render_journey(kb, journey, session, db)
