"""Regenerate contracts/examples from a scripted run against a throwaway database.

Run from apps/api:  uv run python scripts/generate_examples.py
Every value is synthetic (generated IDs, tokens and timestamps); service content comes from the
reviewed seed. The "AI" in these examples is devtools.scripted_model (a deterministic test
stand-in, not a real model), so the text shows the shape of agent output, not its quality.
Examples are validated against the Pydantic contract by tests/test_contract.py.
"""

import json
import os
import sys
import tempfile
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
TMP = Path(tempfile.mkdtemp(prefix="navination-examples-"))
os.environ["DATABASE_URL"] = f"sqlite:///{TMP / 'examples.db'}"
os.environ["AI_PROVIDER"] = "openai_compatible"
os.environ["WEB_FETCH_ENABLED"] = "false"

from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.db.session import get_sessionmaker  # noqa: E402
from app.knowledge.importer import import_bundle  # noqa: E402
from app.knowledge.seed_loader import load_seed  # noqa: E402
from app.main import create_app  # noqa: E402
from app.providers.registry import set_provider_override  # noqa: E402
from devtools.scripted_model import ScriptedModel  # noqa: E402

OUT = ROOT.parents[1] / "contracts" / "examples"
SYNTHETIC_TOKEN = "example-token-not-real"


def main() -> None:
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "alembic"))
    command.upgrade(config, "head")
    with get_sessionmaker()() as db:
        import_bundle(db, load_seed())
    OUT.mkdir(parents=True, exist_ok=True)
    for old in OUT.glob("*.json"):
        old.unlink()
    client = TestClient(create_app())
    set_provider_override(ScriptedModel())

    def save(name: str, request: object | None, response) -> dict:  # type: ignore[no-untyped-def]
        body = response.json() if response.content else None
        if isinstance(body, dict) and "access_token" in body:
            body["access_token"] = SYNTHETIC_TOKEN
        if request is not None:
            (OUT / f"{name}.request.json").write_text(
                json.dumps(request, indent=2, ensure_ascii=False) + "\n"
            )
        (OUT / f"{name}.response.json").write_text(
            json.dumps({"status": response.status_code, "body": body}, indent=2, ensure_ascii=False)
            + "\n"
        )
        return body  # type: ignore[return-value]

    save("health", None, client.get("/api/v1/health"))
    req = {"locale": "en"}
    created = client.post("/api/v1/sessions", json=req)
    token = created.json()["access_token"]
    save("create_session", req, created)
    h = {"Authorization": f"Bearer {token}"}

    def call(method: str, path: str, body: object | None = None):  # type: ignore[no-untyped-def]
        return client.request(method, f"/api/v1{path}", headers=h, json=body)

    save("get_session", None, call("GET", "/session"))
    save("error_unauthorized", None, client.get("/api/v1/session"))
    q = {"query": "My certificate from abroad needs to be accepted", "clarification_answer": None}
    clar = save("discover_needs_clarification", q, call("POST", "/discover", q))
    answer = {
        "query": q["query"],
        "clarification_answer": {
            "discovery_id": clar["id"],
            "question_id": clar["clarification"]["id"],
            "option_id": "university",
        },
    }
    save("discover_clarification_answer", answer, call("POST", "/discover", answer))
    nm = {"query": "I want to renew my driving licence", "clarification_answer": None}
    save("discover_no_match", nm, call("POST", "/discover", nm))
    profile = {
        "emirate": "dubai",
        "residency_status": "resident",
        "life_stage": "worker",
        "degree_issued_outside_uae": True,
    }
    save("put_profile", profile, call("PUT", "/session/profile", profile))
    rq = {
        "query": "I recently arrived and need my overseas degree recognized",
        "clarification_answer": None,
    }
    ready = save("discover_ready", rq, call("POST", "/discover", rq))
    save("get_service", None, call("GET", "/services/mohesr-degree-recognition"))
    jr = {
        "discovery_id": ready["id"],
        "service_ids": [
            "mohesr-degree-recognition",
            "mofa-attestation-abroad",
            "degree-verification-partner",
        ],
    }
    journey = save("create_journey", jr, call("POST", "/journeys", jr))
    steps = {s["service_card"]["service"]["id"]: s["id"] for s in journey["steps"]}
    blocked = {"progress": "completed"}
    save(
        "error_prerequisites_incomplete",
        blocked,
        call(
            "PATCH", f"/journeys/{journey['id']}/steps/{steps['mofa-attestation-abroad']}", blocked
        ),
    )
    upd = {"progress": "completed"}
    save(
        "update_step_progress",
        upd,
        call("PATCH", f"/journeys/{journey['id']}/steps/{steps['uae-pass-account']}", upd),
    )
    mofa_step = next(st for st in journey["steps"] if st["id"] == steps["mofa-attestation-abroad"])
    first, second = (item["id"] for item in mofa_step["checklist"][:2])
    docs = {
        "document_progress": [
            {"document_id": first, "status": "have"},
            {"document_id": second, "status": "missing"},
        ]
    }
    save(
        "update_step_documents",
        docs,
        call("PATCH", f"/journeys/{journey['id']}/steps/{steps['mofa-attestation-abroad']}", docs),
    )
    coach = {
        "client_message_id": str(uuid.UUID(int=1)),
        "message": "What documents do I need for this step?",
        "step_id": steps["mofa-attestation-abroad"],
    }
    save("coach_turn", coach, call("POST", f"/journeys/{journey['id']}/coach", coach))
    unsupported = {
        "client_message_id": str(uuid.UUID(int=2)),
        "message": "Can you recommend a good typing centre near me?",
        "step_id": steps["mohesr-degree-recognition"],
    }
    save(
        "coach_turn_insufficient_evidence",
        unsupported,
        call("POST", f"/journeys/{journey['id']}/coach", unsupported),
    )
    save("list_messages", None, call("GET", f"/journeys/{journey['id']}/messages"))
    ho = {"step_id": steps["mohesr-degree-recognition"], "kind": "official"}
    save("create_handoff", ho, call("POST", f"/journeys/{journey['id']}/handoffs", ho))
    hu = {"step_id": steps["degree-verification-partner"], "kind": "official"}
    save("error_handoff_unavailable", hu, call("POST", f"/journeys/{journey['id']}/handoffs", hu))
    profile2 = {**profile, "emirate": "abu_dhabi"}
    call("PUT", "/session/profile", profile2)
    save("get_journey_stale", None, call("GET", f"/journeys/{journey['id']}"))
    stale_body = {"progress": "in_progress"}
    save(
        "error_context_stale",
        stale_body,
        call("PATCH", f"/journeys/{journey['id']}/steps/{steps['uae-pass-account']}", stale_body),
    )
    save("replan_journey", {}, call("POST", f"/journeys/{journey['id']}/replan", {}))
    save("error_validation", {"query": ""}, call("POST", "/discover", {"query": ""}))
    set_provider_override(None)
    unavailable = {"query": "I need my overseas degree recognized", "clarification_answer": None}
    save("error_ai_unavailable", unavailable, call("POST", "/discover", unavailable))
    set_provider_override(ScriptedModel())
    resp = call("DELETE", "/session")
    (OUT / "delete_session.response.json").write_text(
        json.dumps({"status": resp.status_code, "body": None}, indent=2) + "\n"
    )
    print(f"Wrote examples to {OUT}")


if __name__ == "__main__":
    main()
