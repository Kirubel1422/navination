from fastapi import APIRouter

from app.core.config import get_settings
from app.core.ratelimit import rate_limiter
from app.core.schemas import error_responses
from app.knowledge.repository import get_knowledge
from app.modules.discovery import service
from app.modules.discovery.schemas import DiscoverRequest, Discovery
from app.modules.sessions.deps import CurrentSession, Db

router = APIRouter(tags=["discovery"])


@router.post(
    "/discover", response_model=Discovery, responses=error_responses(401, 404, 409, 422, 429)
)
def discover(body: DiscoverRequest, session: CurrentSession, db: Db) -> Discovery:
    rate_limiter.check(f"discover:{session.id}", get_settings().discover_limit_per_minute)
    return service.discover(db, session, get_knowledge(db), body)
