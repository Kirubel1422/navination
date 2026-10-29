from datetime import timedelta

from sqlalchemy import func, select

from app.core.timeutil import utcnow
from app.db.models import CoachMessage, Discovery, GuestSession, Journey, JourneyStep
from app.db.session import build_engine, get_sessionmaker
from app.modules.sessions.service import cleanup_expired, hash_token
from tests.conftest import DEGREE_QUERY, Guest


def test_create_session_returns_token_once_and_stores_only_hash(client):
    guest = Guest(client)
    assert guest.session["context_revision"] == 0
    assert guest.session["locale"] == "en"
    assert guest.session["profile"] == {
        "emirate": None,
        "residency_status": None,
        "life_stage": None,
        "degree_issued_outside_uae": None,
    }
    assert guest.session["expires_at"].endswith("Z")
    assert guest.token != guest.session["id"]
    with get_sessionmaker()() as db:
        row = db.get(GuestSession, guest.session["id"])
        assert row is not None
        assert row.token_hash == hash_token(guest.token)
        assert guest.token not in row.token_hash
    again = guest.get("/session").json()
    assert "access_token" not in again


def test_missing_and_invalid_tokens_are_rejected(client):
    response = client.get("/api/v1/session")
    assert response.status_code == 401
    body = response.json()["error"]
    assert body["code"] == "UNAUTHORIZED"
    assert body["request_id"].startswith("req_")
    bad = client.get("/api/v1/session", headers={"Authorization": "Bearer not-a-real-token"})
    assert bad.status_code == 401
    assert bad.json()["error"]["code"] == "UNAUTHORIZED"


def test_expired_session_returns_session_expired(client):
    guest = Guest(client)
    with get_sessionmaker()() as db:
        row = db.get(GuestSession, guest.session["id"])
        row.expires_at = utcnow() - timedelta(minutes=1)
        db.commit()
    response = guest.get("/session")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "SESSION_EXPIRED"


def test_locale_change_does_not_change_revision(guest):
    response = guest.patch("/session", json={"locale": "ar"})
    assert response.status_code == 200
    assert response.json()["locale"] == "ar"
    assert response.json()["context_revision"] == 0


def test_profile_revision_increments_only_on_real_change(guest):
    first = guest.set_profile(residency_status="resident")
    assert first["context_revision"] == 1
    same = guest.set_profile(residency_status="resident")
    assert same["context_revision"] == 1
    cleared = guest.set_profile()
    assert cleared["context_revision"] == 2
    assert cleared["profile"]["residency_status"] is None


def test_null_and_false_are_distinct(guest):
    unknown = guest.get("/services/mohesr-degree-recognition").json()
    assert unknown["relevance"] == "more_information_needed"
    assert "degree_issued_outside_uae" in unknown["missing_profile_fields"]
    guest.set_profile(degree_issued_outside_uae=False)
    negative = guest.get("/services/mohesr-degree-recognition").json()
    assert negative["relevance"] == "criterion_mismatch"
    assert negative["missing_profile_fields"] == []


def test_profile_validation(guest):
    missing_field = guest.put("/session/profile", json={"emirate": "dubai"})
    assert missing_field.status_code == 422
    assert missing_field.json()["error"]["code"] == "VALIDATION_ERROR"
    coerced = guest.put(
        "/session/profile",
        json={
            "emirate": None,
            "residency_status": None,
            "life_stage": None,
            "degree_issued_outside_uae": "yes",
        },
    )
    assert coerced.status_code == 422
    extra = guest.put(
        "/session/profile",
        json={
            "emirate": None,
            "residency_status": None,
            "life_stage": None,
            "degree_issued_outside_uae": None,
            "emirates_id": "784-0000",
        },
    )
    assert extra.status_code == 422
    bad_enum = guest.put(
        "/session/profile",
        json={
            "emirate": "atlantis",
            "residency_status": None,
            "life_stage": None,
            "degree_issued_outside_uae": None,
        },
    )
    assert bad_enum.status_code == 422


def test_delete_session_invalidates_token_and_removes_owned_data(guest):
    journey = guest.plan(DEGREE_QUERY, ["mohesr-degree-recognition"])
    guest.post(
        f"/journeys/{journey['id']}/coach",
        json={
            "client_message_id": "8a4f1a52-1f0e-4f1b-9d0c-1b6f7f7f0001",
            "message": "What documents do I need?",
            "step_id": None,
        },
    )
    session_id = guest.session["id"]
    response = guest.delete("/session")
    assert response.status_code == 204
    assert response.content == b""
    assert guest.get("/session").status_code == 401
    with get_sessionmaker()() as db:
        assert db.get(GuestSession, session_id) is None
        assert (
            db.scalar(
                select(func.count())
                .select_from(Discovery)
                .where(Discovery.session_id == session_id)
            )
            == 0
        )
        assert db.get(Journey, journey["id"]) is None
        assert (
            db.scalar(
                select(func.count())
                .select_from(JourneyStep)
                .where(JourneyStep.journey_id == journey["id"])
            )
            == 0
        )
        assert (
            db.scalar(
                select(func.count())
                .select_from(CoachMessage)
                .where(CoachMessage.journey_id == journey["id"])
            )
            == 0
        )


def test_resources_of_other_sessions_return_404(client):
    owner = Guest(client)
    other = Guest(client)
    journey = owner.plan(DEGREE_QUERY, ["mohesr-degree-recognition"])
    assert other.get(f"/journeys/{journey['id']}").status_code == 404
    assert other.get(f"/journeys/{journey['id']}/messages").status_code == 404
    step_id = journey["steps"][0]["id"]
    assert (
        other.patch(
            f"/journeys/{journey['id']}/steps/{step_id}", json={"progress": "in_progress"}
        ).status_code
        == 404
    )
    assert (
        other.post(
            f"/journeys/{journey['id']}/handoffs", json={"step_id": step_id, "kind": "official"}
        ).status_code
        == 404
    )
    discovery = owner.discover(DEGREE_QUERY)
    response = other.post(
        "/journeys",
        json={"discovery_id": discovery["id"], "service_ids": ["mohesr-degree-recognition"]},
    )
    assert response.status_code == 404


def test_state_survives_a_new_engine(guest):
    """Simulates a backend restart: a fresh engine reads the same persisted rows."""
    journey = guest.plan(DEGREE_QUERY, ["mohesr-degree-recognition"])
    from app.core.config import get_settings

    engine = build_engine(get_settings().database_url)
    with engine.connect() as conn:
        assert (
            conn.execute(select(Journey.id).where(Journey.id == journey["id"])).scalar()
            == journey["id"]
        )
    engine.dispose()
    assert guest.get(f"/journeys/{journey['id']}").status_code == 200


def test_cleanup_removes_only_expired_sessions(client):
    live = Guest(client)
    expired = Guest(client)
    with get_sessionmaker()() as db:
        db.get(GuestSession, expired.session["id"]).expires_at = utcnow() - timedelta(hours=1)
        db.commit()
        removed = cleanup_expired(db)
        assert removed >= 1
        assert db.get(GuestSession, expired.session["id"]) is None
        assert db.get(GuestSession, live.session["id"]) is not None


def test_session_creation_is_rate_limited(client, monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "session_create_limit_per_minute", 2)
    assert client.post("/api/v1/sessions", json={"locale": "en"}).status_code == 201
    assert client.post("/api/v1/sessions", json={"locale": "en"}).status_code == 201
    limited = client.post("/api/v1/sessions", json={"locale": "en"})
    assert limited.status_code == 429
    assert limited.json()["error"]["code"] == "RATE_LIMITED"


def test_unexpected_request_fields_and_oversized_bodies(client):
    assert client.post("/api/v1/sessions", json={"locale": "en", "admin": True}).status_code == 422
    big = client.post(
        "/api/v1/sessions",
        content=b'{"locale":"en","x":"' + b"a" * 40_000 + b'"}',
        headers={"Content-Type": "application/json"},
    )
    assert big.status_code == 413
    assert big.json()["error"]["code"] == "VALIDATION_ERROR"
