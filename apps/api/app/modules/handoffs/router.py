from fastapi import APIRouter, Path, status

from app.core.schemas import error_responses
from app.knowledge.repository import get_knowledge
from app.modules.handoffs import service
from app.modules.handoffs.schemas import Handoff, HandoffRequest
from app.modules.journeys.service import get_owned_journey
from app.modules.sessions.deps import CurrentSession, Db

router = APIRouter(tags=["handoffs"])


@router.post(
    "/journeys/{journey_id}/handoffs",
    status_code=status.HTTP_201_CREATED,
    response_model=Handoff,
    responses=error_responses(401, 404, 409, 422),
)
def create_handoff(
    body: HandoffRequest, session: CurrentSession, db: Db, journey_id: str = Path(max_length=80)
) -> Handoff:
    journey = get_owned_journey(db, session, journey_id)
    return service.create_handoff(db, session, get_knowledge(db), journey, body)
