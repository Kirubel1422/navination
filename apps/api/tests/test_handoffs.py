from app.providers.registry import set_provider_override
from tests.conftest import BABY_QUERY, DEGREE_QUERY, step_for
from tests.fakes import QueueModel, call, fake_web, html, turn


def test_official_and_support_handoffs_resolve_from_records(guest):
    journey = guest.plan(DEGREE_QUERY, ["mohesr-degree-recognition"])
    step = step_for(journey, "mohesr-degree-recognition")
    official = guest.post(
        f"/journeys/{journey['id']}/handoffs", json={"step_id": step["id"], "kind": "official"}
    )
    assert official.status_code == 201
    assert official.json()["url"].startswith("https://www.mohesr.gov.ae/")
    assert "Ministry of Higher Education" in official.json()["label"]
    support = guest.post(
        f"/journeys/{journey['id']}/handoffs", json={"step_id": step["id"], "kind": "support"}
    )
    assert support.status_code == 201 and support.json()["url"].startswith("https://u.ae/")


def test_unverified_or_missing_destinations_are_unavailable(guest):
    journey = guest.plan(DEGREE_QUERY, ["degree-verification-partner"])
    step = step_for(journey, "degree-verification-partner")
    response = guest.post(
        f"/journeys/{journey['id']}/handoffs", json={"step_id": step["id"], "kind": "official"}
    )
    assert response.status_code == 409 and response.json()["error"]["code"] == "HANDOFF_UNAVAILABLE"
    baby = guest.plan(BABY_QUERY, ["birth-registration"])
    reg = step_for(baby, "birth-registration")
    assert (
        guest.post(
            f"/journeys/{baby['id']}/handoffs", json={"step_id": reg["id"], "kind": "official"}
        ).status_code
        == 409
    )


def test_ai_found_service_hands_off_to_the_official_page_it_read(guest):
    from app.agent.web import set_official_web_override
    from tests.test_discovery import GOLDEN, golden_submission

    set_official_web_override(
        fake_web(
            {
                GOLDEN: html(
                    "Golden visa",
                    "The golden visa offers long-term residence in the UAE for eligible groups.",
                )
            }
        )
    )
    set_provider_override(
        QueueModel(
            turn(call("fetch_official_page", {"url": GOLDEN})),
            turn(call("submit_discovery", golden_submission())),
        )
    )
    discovery = guest.discover("golden visa")
    service_id = discovery["results"][0]["service"]["id"]
    from devtools.scripted_model import ScriptedModel

    set_provider_override(ScriptedModel())
    created = guest.post(
        "/journeys", json={"discovery_id": discovery["id"], "service_ids": [service_id]}
    )
    assert created.status_code == 201, created.text
    journey = created.json()
    step = journey["steps"][0]
    handoff = guest.post(
        f"/journeys/{journey['id']}/handoffs", json={"step_id": step["id"], "kind": "official"}
    )
    assert handoff.status_code == 201 and handoff.json()["url"] == GOLDEN


def test_arbitrary_destinations_are_refused(guest):
    journey = guest.plan(DEGREE_QUERY, ["mohesr-degree-recognition"])
    step = journey["steps"][0]
    url = f"/journeys/{journey['id']}/handoffs"
    assert (
        guest.post(
            url, json={"step_id": step["id"], "kind": "official", "url": "https://evil.example"}
        ).status_code
        == 422
    )
    assert guest.post(url, json={"step_id": step["id"], "kind": "custom"}).status_code == 422
    assert guest.post(url, json={"step_id": "stp_x", "kind": "official"}).status_code == 404
