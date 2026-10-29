"""Guest session lifecycle: opaque bearer tokens, hashed at rest, with explicit expiry."""

import hashlib
import secrets
from datetime import timedelta

from sqlalchemy import delete, select
from sqlalchemy.orm import Session as DbSession

from app.core.config import get_settings
from app.core.errors import session_expired, unauthorized
from app.core.timeutil import as_utc, utcnow
from app.db.models import GuestSession
from app.modules.sessions.schemas import Profile, ProfileRequest, Session

PROFILE_FIELDS = ("emirate", "residency_status", "life_stage", "degree_issued_outside_uae")


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def new_id(prefix: str) -> str:
    return f"{prefix}_{secrets.token_urlsafe(12)}"


def create_session(db: DbSession, locale: str) -> tuple[GuestSession, str]:
    token = secrets.token_urlsafe(32)
    now = utcnow()
    session = GuestSession(
        id=new_id("ses"),
        token_hash=hash_token(token),
        locale=locale,
        created_at=now,
        expires_at=now + timedelta(hours=get_settings().session_ttl_hours),
        context_revision=0,
    )
    db.add(session)
    db.commit()
    return session, token


def authenticate(db: DbSession, authorization: str | None) -> GuestSession:
    if not authorization:
        raise unauthorized()
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip() or len(token) > 256:
        raise unauthorized()
    session = db.scalar(
        select(GuestSession).where(GuestSession.token_hash == hash_token(token.strip()))
    )
    if session is None:
        raise unauthorized()
    if as_utc(session.expires_at) <= utcnow():
        raise session_expired()
    return session


def profile_of(session: GuestSession) -> dict:
    return {name: getattr(session, name) for name in PROFILE_FIELDS}


def to_schema(session: GuestSession) -> Session:
    return Session(
        id=session.id,
        locale=session.locale,  # type: ignore[arg-type]
        expires_at=session.expires_at,
        context_revision=session.context_revision,
        profile=Profile(**profile_of(session)),
    )


def replace_profile(db: DbSession, session: GuestSession, profile: ProfileRequest) -> bool:
    """Replace the profile. context_revision only increments when a value actually changes."""
    new_values = profile.model_dump()
    changed = any(getattr(session, k) != v for k, v in new_values.items())
    if changed:
        for key, value in new_values.items():
            setattr(session, key, value)
        session.context_revision += 1
    db.commit()
    return changed


def delete_session(db: DbSession, session: GuestSession) -> None:
    """Deletes the session and everything it owns in one transaction (FK cascades)."""
    db.delete(session)
    db.commit()


def cleanup_expired(db: DbSession) -> int:
    result = db.execute(delete(GuestSession).where(GuestSession.expires_at <= utcnow()))
    db.commit()
    return result.rowcount or 0
