from fastapi import APIRouter, Path

from app.core.config import get_settings
from app.core.ratelimit import rate_limiter
from app.core.schemas import error_responses
from app.knowledge.repository import get_knowledge
from app.modules.coach import service
from app.modules.coach.schemas import CoachRequest, CoachTurn, MessageList
from app.modules.journeys.service import get_owned_journey
from app.modules.sessions.deps import CurrentSession, Db

router = APIRouter(tags=["coach"])


@router.get(
    "/journeys/{journey_id}/messages",
    response_model=MessageList,
    responses=error_responses(401, 404),
)
def list_messages(
    session: CurrentSession, db: Db, journey_id: str = Path(max_length=80)
) -> MessageList:
    journey = get_owned_journey(db, session, journey_id)
    return MessageList(items=service.list_messages(db, get_knowledge(db), journey, session.locale))


@router.post(
    "/journeys/{journey_id}/coach",
    response_model=CoachTurn,
    responses=error_responses(401, 404, 409, 422, 429, 503),
)
def coach(
    body: CoachRequest, session: CurrentSession, db: Db, journey_id: str = Path(max_length=80)
) -> CoachTurn:
    journey = get_owned_journey(db, session, journey_id)
    rate_limiter.check(f"coach:{session.id}", get_settings().coach_limit_per_minute)
    return service.coach_turn(db, session, get_knowledge(db), journey, body)
