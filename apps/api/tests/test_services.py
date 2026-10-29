from app.providers.registry import set_provider_override
from tests.conftest import DEGREE_QUERY
from tests.fakes import RecordingModel


def test_detail_reuses_the_current_ai_assessment(guest):
    guest.discover(DEGREE_QUERY)
    recorder = RecordingModel()
    set_provider_override(recorder)
    card = guest.get("/services/mohesr-degree-recognition").json()
    assert recorder.payloads == []  # no new model call: the search's assessment is reused
    service = card["service"]
    assert service["origin"] == "catalog"
    assert service["fee_text"] is None and service["processing_time_text"] is None
    sources = {s["id"]: s for s in service["sources"]}
    assert sources["src-uae-higher-ed-recognition"]["source_updated_at"] == "2026-10-22"
    assert sources["src-mohesr-recognition-card"]["checked_at"].endswith("Z")


def test_detail_asks_the_agent_after_a_profile_change(guest):
    guest.discover(DEGREE_QUERY)
    guest.set_profile(degree_issued_outside_uae=False)
    recorder = RecordingModel()
    set_provider_override(recorder)
    card = guest.get("/services/mohesr-degree-recognition").json()
    assert (
        recorder.payloads and recorder.payloads[0]["PROFILE"]["degree_issued_outside_uae"] is False
    )
    assert card["relevance"] == "criterion_mismatch"
    assert "Ministry of Higher Education" in card["authority_notice"]


def test_null_and_false_reach_the_agent_distinctly(guest):
    recorder = RecordingModel()
    set_provider_override(recorder)
    unknown = guest.get("/services/mohesr-degree-recognition").json()
    assert recorder.payloads[-1]["PROFILE"]["degree_issued_outside_uae"] is None
    assert "degree_issued_outside_uae" in unknown["missing_profile_fields"]
    guest.set_profile(degree_issued_outside_uae=False)
    negative = guest.get("/services/mohesr-degree-recognition").json()
    assert recorder.payloads[-1]["PROFILE"]["degree_issued_outside_uae"] is False
    assert negative["missing_profile_fields"] == []


def test_needs_review_records_are_labelled(guest):
    card = guest.get("/services/degree-verification-partner").json()
    assert card["service"]["verification_status"] == "needs_review"
    assert any("not confirmed" in r["text"] for r in card["reasons"])


def test_readiness_comes_from_verified_rules(guest):
    assert (
        guest.get("/services/mofa-attestation-abroad").json()["readiness"] == "prerequisites_needed"
    )
    assert guest.get("/services/newborn-residence-permit").json()["readiness"] == "unknown"


def test_unknown_service_and_ai_unavailable(guest):
    assert guest.get("/services/does-not-exist").status_code == 404
    set_provider_override(None)
    response = guest.get("/services/birth-registration")
    assert response.status_code == 503


def test_localized_service_content(client):
    from tests.conftest import Guest

    guest = Guest(client, locale="ar")
    card = guest.get("/services/birth-registration").json()
    assert "شهادة الميلاد" in card["service"]["title"]
