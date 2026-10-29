"""How the optional profile shapes a plan: tailored steps and services that are not needed,
derived from the reviewed catalog (the persona: expat parents of a newborn in Umm Al Quwain)."""

from tests.conftest import BABY_QUERY

BABY = [
    "birth-registration",
    "birth-certificate-attestation",
    "newborn-passport-embassy",
    "newborn-residence-permit",
]


def _profile(guest, **answers):  # type: ignore[no-untyped-def]
    body = {
        "emirate": None,
        "residency_status": None,
        "life_stage": None,
        "degree_issued_outside_uae": None,
    }
    response = guest.put("/session/profile", {**body, **answers})
    assert response.status_code == 200, response.text


def _steps(journey: dict) -> dict:
    return {s["service_card"]["service"]["id"]: s for s in journey["steps"]}


def test_a_resident_family_gets_the_residency_stages_and_skips_the_citizen_bundle(guest):
    _profile(guest, emirate="umm_al_quwain", residency_status="resident", life_stage="parent")
    journey = guest.plan(BABY_QUERY, BABY)
    steps = _steps(journey)
    assert "residency_status" in steps["newborn-residence-permit"]["tailored_by"]
    assert "residency_status" in steps["newborn-passport-embassy"]["tailored_by"]
    # The verified "passport before residence permit" rule applies to residents.
    assert (
        steps["newborn-passport-embassy"]["id"]
        in steps["newborn-residence-permit"]["prerequisite_step_ids"]
    )
    effects = {e["field"]: e for e in journey["personalization"]}
    assert effects["residency_status"]["value"] == "resident"
    assert steps["newborn-residence-permit"]["id"] in effects["residency_status"]["step_ids"]
    assert effects["emirate"]["value"] == "umm_al_quwain"
    skipped = {s["service_id"]: s for s in journey["skipped"]}
    assert (
        skipped["mabrouk-ma-yak"]["field"] == "residency_status"
        and skipped["mabrouk-ma-yak"]["reason"]
    )


def test_without_a_profile_nothing_is_claimed(guest):
    journey = guest.plan(BABY_QUERY, ["birth-registration"])
    assert journey["personalization"] == [] and journey["skipped"] == []
    assert all(s["tailored_by"] == [] and s["tailored_note"] is None for s in journey["steps"])


def test_an_emirate_answer_adds_the_catalog_guidance_for_that_emirate(guest):
    _profile(guest, emirate="dubai", residency_status="resident")
    journey = guest.plan(BABY_QUERY, ["birth-registration"])
    step = _steps(journey)["birth-registration"]
    assert "emirate" in step["tailored_by"] and "Dubai" in step["tailored_note"]
