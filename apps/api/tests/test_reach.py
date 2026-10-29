"""Phone contacts and nearby centres: numbers only from pages the agent read, centres only from
the places tool, and the person's location never stored."""

import json

import httpx
import pytest

from app.agent import places as places_module
from app.agent.contacts import appears_in, national, plausible, tel_href
from app.agent.web import set_official_web_override
from app.core.config import get_settings
from app.providers.registry import set_provider_override
from devtools.scripted_model import ScriptedModel
from tests.conftest import DEGREE_QUERY
from tests.fakes import QueueModel, call, fake_web, html, tool_results, turn

CONTACT = "https://www.mohesr.gov.ae/en/contact-us"
CONTACT_PAGE = html(
    "Contact us",
    "Customer service: call 800 51115 (Sunday to Thursday). Outside the UAE: +971 4 295 1888. "
    "Email info@mohesr.gov.ae. Last updated 2025-03-01.",
)
L = lambda text: {"en": text, "ar": text}  # noqa: E731


def _discovery(reach: dict) -> dict:
    return {
        "status": "ready",
        "interpreted_need": L("Recognise a degree issued abroad"),
        "answer": L("Apply to MoHESR for recognition; their customer service is on 800 51115."),
        "answer_refs": [CONTACT],
        "results": [
            {
                "kind": "catalog",
                "service_id": "mohesr-degree-recognition",
                "assessment": {
                    "relevance": "potentially_relevant",
                    "reasons": [{"text": L("Matches your request."), "source_refs": []}],
                },
                "reach": reach,
            }
        ],
    }


def _contact(phone: str) -> dict:
    return {"label": L("MoHESR customer service"), "phone": phone, "source_ref": CONTACT}


def test_number_helpers():
    assert national("+971 4 295 1888") == national("04-295 1888") == "42951888"
    assert plausible("800 51115") and not plausible("2025") and not plausible("2025-03-01")
    assert tel_href("800 51115") == "tel:80051115"
    assert tel_href("04 295 1888") == "tel:+97142951888"
    assert appears_in("+97142951888", ["call 04 295 1888"])
    assert not appears_in("800 51116", ["call 800 51115"])


def test_contact_numbers_must_appear_on_a_page_the_agent_read(guest):
    set_official_web_override(fake_web({CONTACT: CONTACT_PAGE}))
    model = QueueModel(
        # A guessed number (and before reading any page) is rejected...
        turn(call("submit_discovery", _discovery({"contacts": [_contact("800 99999")]}))),
        turn(call("find_contacts", {"url": CONTACT})),
        turn(call("submit_discovery", _discovery({"contacts": [_contact("800 99999")]}))),
        # ...and the number published on the page is accepted.
        turn(
            call(
                "submit_discovery",
                _discovery({"contacts": [_contact("800 51115")], "map_query": "MoHESR office"}),
            )
        ),
    )
    set_provider_override(model)
    result = guest.discover(DEGREE_QUERY)

    found = tool_results(model.requests[2][0])
    assert any(r.get("url") == CONTACT and r["phones"][0]["phone"] == "800 51115" for r in found)
    assert "does not appear" in json.dumps(tool_results(model.requests[3][0])[-1])
    reach = result["results"][0]["reach"]
    assert reach["contacts"] == [
        {
            "label": "MoHESR customer service",
            "phone": "800 51115",
            "tel": "tel:80051115",
            "email": None,
            "hours": None,
            "source_url": CONTACT,
            "source_title": "Contact us",
        }
    ]
    assert reach["map_query"] == "MoHESR office" and reach["centers"] == []
    assert result["answer"].startswith("Apply to MoHESR")
    assert result["answer_sources"][0]["url"] == CONTACT
    # Contacts found while searching stay with the service in the plan.
    set_provider_override(ScriptedModel())
    plan = guest.post(
        "/journeys",
        json={"discovery_id": result["id"], "service_ids": ["mohesr-degree-recognition"]},
    )
    assert plan.status_code == 201, plan.text
    step = next(
        s
        for s in plan.json()["steps"]
        if s["service_card"]["service"]["id"] == "mohesr-degree-recognition"
    )
    assert step["service_card"]["reach"]["contacts"][0]["phone"] == "800 51115"


PHOTON = {
    "features": [
        {
            "geometry": {"coordinates": [55.3259, 25.2653]},
            "properties": {
                "osm_type": "N",
                "osm_id": 101,
                "name": "Tasheel Al Muraqqabat",
                "osm_key": "office",
                "osm_value": "government",
                "street": "Al Muraqqabat Road",
                "city": "Dubai",
                "countrycode": "AE",
            },
        },
        {
            "geometry": {"coordinates": [55.2548, 25.2201]},
            "properties": {
                "osm_type": "N",
                "osm_id": 102,
                "name": "American Dental Clinic",
                "osm_key": "amenity",
                "osm_value": "dentist",
                "countrycode": "AE",
            },
        },
    ]
}


@pytest.fixture
def places_on(monkeypatch: pytest.MonkeyPatch) -> list[httpx.Request]:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=PHOTON)

    monkeypatch.setattr(get_settings(), "places_enabled", True)
    monkeypatch.setattr(
        places_module,
        "_instance",
        places_module.Places(5, httpx.Client(transport=httpx.MockTransport(handler))),
    )
    return seen


def test_nearby_returns_only_real_centres_and_never_stores_the_location(guest, places_on):
    set_official_web_override(fake_web({CONTACT: CONTACT_PAGE}))
    nearby = {
        "message": L("Tasheel Al Muraqqabat is the closest centre; call MoHESR first if unsure."),
        "reach": {
            "contacts": [_contact("04 295 1888")],
            "centers": [{"place_id": "osm-N101", "note": L("Handles typing and applications.")}],
            "map_query": "Tasheel centre",
        },
    }
    model = QueueModel(
        turn(
            call(
                "submit_nearby",
                {**nearby, "reach": {**nearby["reach"], "centers": [{"place_id": "osm-N999"}]}},
            )
        ),
        turn(
            call("find_service_centers", {"query": "Tasheel"}),
            call("find_contacts", {"url": CONTACT}),
        ),
        turn(call("submit_nearby", nearby)),
    )
    set_provider_override(model)
    response = guest.post(
        "/services/mohesr-degree-recognition/nearby",
        json={"location": {"lat": 25.2611, "lng": 55.3127}, "request": "open on Saturday"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert "was not returned by find_service_centers" in json.dumps(
        tool_results(model.requests[1][0])[-1]
    )
    places = next(r for r in tool_results(model.requests[2][0]) if "places" in r)["places"]
    assert [p["name"] for p in places] == ["Tasheel Al Muraqqabat"]  # the dentist is filtered out
    assert places[0]["distance_km"] is not None
    center = body["reach"]["centers"][0]
    assert center["name"] == "Tasheel Al Muraqqabat" and center["lat"] == 25.2653
    assert body["reach"]["contacts"][0]["tel"] == "tel:+97142951888"
    # Only a rounded bias point leaves the server, and nothing about the location is stored.
    assert places_on and places_on[0].url.params["lat"] == "25.26"
    assert "25.2611" not in json.dumps(guest.get("/session").json())


def test_nearby_rejects_bad_locations(guest):
    response = guest.post(
        "/services/mohesr-degree-recognition/nearby", json={"location": {"lat": 200, "lng": 55}}
    )
    assert response.status_code == 422
