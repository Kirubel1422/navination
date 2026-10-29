from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session as DbSession

from app.db.models import GuestSession
from app.db.session import get_db
from app.modules.sessions.service import authenticate

Db = Annotated[DbSession, Depends(get_db)]
bearer = HTTPBearer(auto_error=False, scheme_name="GuestSessionToken")


def current_session(
    db: Db,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> GuestSession:
    header = f"{credentials.scheme} {credentials.credentials}" if credentials else None
    return authenticate(db, header)


CurrentSession = Annotated[GuestSession, Depends(current_session)]
