from fastapi import APIRouter, Request, Response, status

from app.core.config import get_settings
from app.core.ratelimit import rate_limiter
from app.core.schemas import error_responses
from app.modules.sessions import service
from app.modules.sessions.deps import CurrentSession, Db
from app.modules.sessions.schemas import (
    CreateSessionRequest,
    CreateSessionResponse,
    ProfileRequest,
    Session,
    UpdateSessionRequest,
)

router = APIRouter(tags=["sessions"])


@router.post(
    "/sessions",
    status_code=status.HTTP_201_CREATED,
    response_model=CreateSessionResponse,
    responses=error_responses(422, 429),
)
def create_session(body: CreateSessionRequest, request: Request, db: Db) -> CreateSessionResponse:
    client = request.client.host if request.client else "unknown"
    rate_limiter.check(f"sessions:{client}", get_settings().session_create_limit_per_minute)
    session, token = service.create_session(db, body.locale)
    return CreateSessionResponse(session=service.to_schema(session), access_token=token)


@router.get("/session", response_model=Session, responses=error_responses(401))
def get_session(session: CurrentSession) -> Session:
    return service.to_schema(session)


@router.patch("/session", response_model=Session, responses=error_responses(401, 422))
def update_session(body: UpdateSessionRequest, session: CurrentSession, db: Db) -> Session:
    # Locale changes never alter context_revision.
    session.locale = body.locale
    db.commit()
    return service.to_schema(session)


@router.put("/session/profile", response_model=Session, responses=error_responses(401, 422))
def replace_profile(body: ProfileRequest, session: CurrentSession, db: Db) -> Session:
    service.replace_profile(db, session, body)
    return service.to_schema(session)


@router.delete(
    "/session",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    responses=error_responses(401),
)
def delete_session(session: CurrentSession, db: Db) -> Response:
    service.delete_session(db, session)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
