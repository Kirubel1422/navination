import os
import tempfile
from collections.abc import Iterator
from pathlib import Path

import pytest

_TMP = Path(tempfile.mkdtemp(prefix="navination-test-"))
os.environ["DATABASE_URL"] = f"sqlite:///{_TMP / 'test.db'}"
os.environ["APP_ENV"] = "test"
os.environ["AI_PROVIDER"] = "openai_compatible"
# Explicit empty values beat apps/api/.env, so a developer's real key/model never leaks into tests.
for name in (
    "AI_API_KEY",
    "AI_MODEL",
    "AI_PROVIDER_BASE_URL",
    "AI_REASONING_EFFORT",
    "AI_MAX_OUTPUT_TOKENS",
    "WEB_SEARCH_API_KEY",
):
    os.environ[name] = ""
os.environ["WEB_FETCH_ENABLED"] = "false"  # tests never touch the network
os.environ["WEB_SEARCH_PROVIDER"] = "none"
os.environ["BAYANAT_ENABLED"] = "false"
os.environ["AJMAN_DATA_ENABLED"] = "false"
os.environ["PLACES_ENABLED"] = "false"
os.environ["OPEN_DATA_SYNC"] = "false"  # no portal calls; bundled copies are imported

from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.agent.web import set_official_web_override  # noqa: E402
from app.core.config import API_ROOT  # noqa: E402
from app.core.ratelimit import rate_limiter  # noqa: E402
from app.db.session import get_sessionmaker  # noqa: E402
from app.knowledge.importer import import_bundle  # noqa: E402
from app.knowledge.seed_loader import load_seed  # noqa: E402
from app.main import create_app  # noqa: E402
from app.opendata.sync import import_bundled  # noqa: E402
from app.providers.registry import set_provider_override  # noqa: E402
from devtools.scripted_model import ScriptedModel  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def database() -> Iterator[None]:
    config = Config(str(API_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(API_ROOT / "alembic"))
    command.upgrade(config, "head")
    with get_sessionmaker()() as db:
        import_bundle(db, load_seed())
        import_bundled(db)
    yield


@pytest.fixture(autouse=True)
def _reset() -> Iterator[None]:
    """Every test runs the real agent path against the scripted test model unless it overrides it."""
    rate_limiter.reset()
    set_provider_override(ScriptedModel())
    set_official_web_override(None)
    yield
    set_provider_override(None, enabled=False)
    set_official_web_override(None)


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(create_app()) as test_client:
        yield test_client


class Guest:
    """A guest session bound to a test client."""

    def __init__(self, client: TestClient, locale: str = "en") -> None:
        self.client = client
        response = client.post("/api/v1/sessions", json={"locale": locale})
        assert response.status_code == 201, response.text
        body = response.json()
        self.token = body["access_token"]
        self.session = body["session"]

    @property
    def headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}"}

    def get(self, path: str, **kw):  # type: ignore[no-untyped-def]
        return self.client.get(f"/api/v1{path}", headers=self.headers, **kw)

    def post(self, path: str, json=None, **kw):  # type: ignore[no-untyped-def]
        return self.client.post(f"/api/v1{path}", headers=self.headers, json=json, **kw)

    def put(self, path: str, json=None):  # type: ignore[no-untyped-def]
        return self.client.put(f"/api/v1{path}", headers=self.headers, json=json)

    def patch(self, path: str, json=None):  # type: ignore[no-untyped-def]
        return self.client.patch(f"/api/v1{path}", headers=self.headers, json=json)

    def delete(self, path: str):  # type: ignore[no-untyped-def]
        return self.client.delete(f"/api/v1{path}", headers=self.headers)

    def set_profile(self, **values):  # type: ignore[no-untyped-def]
        profile = {
            "emirate": None,
            "residency_status": None,
            "life_stage": None,
            "degree_issued_outside_uae": None,
        }
        profile.update(values)
        response = self.put("/session/profile", json=profile)
        assert response.status_code == 200, response.text
        return response.json()

    def discover(self, query: str, answer: dict | None = None) -> dict:
        response = self.post("/discover", json={"query": query, "clarification_answer": answer})
        assert response.status_code == 200, response.text
        return response.json()

    def plan(self, query: str, service_ids: list[str]) -> dict:
        discovery = self.discover(query)
        assert discovery["status"] == "ready", discovery
        response = self.post(
            "/journeys", json={"discovery_id": discovery["id"], "service_ids": service_ids}
        )
        assert response.status_code == 201, response.text
        return response.json()


DEGREE_QUERY = "I recently arrived and need my overseas degree recognized"
BABY_QUERY = "We just had a baby. What do we need to register?"


@pytest.fixture
def guest(client: TestClient) -> Guest:
    return Guest(client)


def step_for(journey: dict, service_id: str) -> dict:
    return next(s for s in journey["steps"] if s["service_card"]["service"]["id"] == service_id)
