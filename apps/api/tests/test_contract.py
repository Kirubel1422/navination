"""The committed contract, examples and runtime must agree."""

import json
from pathlib import Path

import pytest
from pydantic import BaseModel

from app.cli import CONTRACT_PATH, export_openapi
from app.core.config import CONTRACT_VERSION
from app.core.schemas import ErrorEnvelope
from app.main import Health
from app.modules.coach.schemas import CoachRequest, CoachTurn, MessageList
from app.modules.discovery.schemas import DiscoverRequest, Discovery
from app.modules.handoffs.schemas import Handoff, HandoffRequest
from app.modules.journeys.schemas import (
    CreateJourneyRequest,
    Journey,
    ReplanRequest,
    StepUpdateRequest,
)
from app.modules.services.schemas import ServiceCard
from app.modules.sessions.schemas import (
    CreateSessionRequest,
    CreateSessionResponse,
    ProfileRequest,
    Session,
)

EXAMPLES = Path(CONTRACT_PATH).parent / "examples"

MODELS: dict[str, tuple[type[BaseModel] | None, type[BaseModel] | None]] = {
    "health": (None, Health),
    "create_session": (CreateSessionRequest, CreateSessionResponse),
    "get_session": (None, Session),
    "put_profile": (ProfileRequest, Session),
    "discover_needs_clarification": (DiscoverRequest, Discovery),
    "discover_clarification_answer": (DiscoverRequest, Discovery),
    "discover_no_match": (DiscoverRequest, Discovery),
    "discover_ready": (DiscoverRequest, Discovery),
    "get_service": (None, ServiceCard),
    "create_journey": (CreateJourneyRequest, Journey),
    "update_step_progress": (StepUpdateRequest, Journey),
    "update_step_documents": (StepUpdateRequest, Journey),
    "get_journey_stale": (None, Journey),
    "replan_journey": (ReplanRequest, Journey),
    "coach_turn": (CoachRequest, CoachTurn),
    "coach_turn_insufficient_evidence": (CoachRequest, CoachTurn),
    "list_messages": (None, MessageList),
    "create_handoff": (HandoffRequest, Handoff),
    "error_unauthorized": (None, ErrorEnvelope),
    "error_prerequisites_incomplete": (StepUpdateRequest, ErrorEnvelope),
    "error_handoff_unavailable": (HandoffRequest, ErrorEnvelope),
    "error_context_stale": (StepUpdateRequest, ErrorEnvelope),
    "error_validation": (None, ErrorEnvelope),
    "error_ai_unavailable": (DiscoverRequest, ErrorEnvelope),
    "delete_session": (None, None),
}


def test_committed_openapi_matches_runtime():
    committed = json.loads(Path(CONTRACT_PATH).read_text(encoding="utf-8"))
    assert committed == json.loads(json.dumps(export_openapi()))
    assert committed["info"]["version"] == CONTRACT_VERSION == "1.1.0"


def test_every_example_is_listed():
    names = {p.name.split(".")[0] for p in EXAMPLES.glob("*.json")}
    assert names == set(MODELS)


@pytest.mark.parametrize("name", sorted(MODELS))
def test_examples_validate_against_contract(name):
    request_model, response_model = MODELS[name]
    request_file = EXAMPLES / f"{name}.request.json"
    if request_model is not None:
        request_model.model_validate_json(request_file.read_text(encoding="utf-8"), strict=False)
    response = json.loads((EXAMPLES / f"{name}.response.json").read_text(encoding="utf-8"))
    if response_model is None:
        assert response["body"] is None and response["status"] == 204
    else:
        response_model.model_validate(response["body"])
        if response_model is ErrorEnvelope:
            assert response["status"] >= 400


def test_examples_cover_key_states():
    def body(name: str) -> dict:
        return json.loads((EXAMPLES / f"{name}.response.json").read_text(encoding="utf-8"))["body"]

    assert body("discover_ready")["status"] == "ready"
    assert body("discover_needs_clarification")["status"] == "needs_clarification"
    assert body("discover_no_match")["status"] == "no_match"
    assert body("get_journey_stale")["is_stale"] is True
    assert body("error_handoff_unavailable")["error"]["code"] == "HANDOFF_UNAVAILABLE"
    assert body("coach_turn_insufficient_evidence")["grounding_status"] == "insufficient_evidence"
    assert body("error_ai_unavailable")["error"]["code"] == "SERVICE_UNAVAILABLE"
    assert body("discover_ready")["mode"] == "ai" and body("discover_ready")["agent_steps"]
    assert body("create_journey")["stages"] and body("create_journey")["agent_steps"]
    journey = body("create_journey")
    sources = {s["id"] for st in journey["steps"] for s in st["service_card"]["service"]["sources"]}
    for dep in journey["dependencies"]:
        assert set(dep["source_ids"]) <= sources


def test_runtime_validation_errors_use_envelope(client):
    response = client.post("/api/v1/sessions", json={"locale": "fr"})
    assert response.status_code == 422
    ErrorEnvelope.model_validate(response.json())
    missing = client.get("/api/v1/nope")
    assert missing.status_code == 404
    ErrorEnvelope.model_validate(missing.json())
