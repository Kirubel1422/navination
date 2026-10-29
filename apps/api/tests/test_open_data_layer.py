"""The open data layer: parsing, insights, sync with provenance and fallbacks, public endpoints,
the navigation-gaps dataset (anonymous) and the agent's use of open-data figures."""

import io
import json

import httpx
import openpyxl
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.agent.ajman import AjmanData
from app.agent.bayanat import Bayanat
from app.db.models import Base, NavEvent, OdDataset, OdSnapshot
from app.opendata import insights
from app.opendata.sync import import_bundled, is_stale, run_sync
from app.opendata.tables import DatasetSpec, TableError, catalogue, parse_table
from app.providers.registry import set_provider_override
from tests.conftest import DEGREE_QUERY, Guest
from tests.fakes import RecordingModel


def _spec(**table) -> DatasetSpec:  # type: ignore[no-untyped-def]
    return DatasetSpec(
        key="t",
        portal="bayanat",
        title="T",
        publisher="P",
        url="https://bayanat.ae/x",
        resource={},
        table=table,
    )


def _xlsx(rows: list[list]) -> bytes:  # type: ignore[type-arg]
    book = openpyxl.Workbook()
    sheet = book.active
    sheet.title = "Data"
    for row in rows:
        sheet.append(row)
    buffer = io.BytesIO()
    book.save(buffer)
    return buffer.getvalue()


def test_parse_table_finds_the_header_keeps_columns_and_list_cells():
    content = _xlsx(
        [
            ["Statistics Centre"],
            [],
            ["Year", "Emirate En", "Note", "Total"],
            [2024, " Dubai ", "a\nb\nc", 1200],
            [2023, "Ajman", None, 7.0],
            [],
            ["footer"],
        ]
    )
    columns, rows = parse_table(
        content,
        _spec(
            format="xlsx",
            sheet="Data",
            header_contains="emirate en",
            keep=["Year", "Emirate En", "Total", "Note"],
        ),
    )
    assert columns == ["Year", "Emirate En", "Total", "Note"]
    assert rows == [[2024, "Dubai", 1200, "a; b; c"], [2023, "Ajman", 7, None]]
    csv_rows = parse_table(
        b"NAME,Jan-25,TOTAL\nX,3,3\n", _spec(format="csv", header_contains="name")
    )
    assert csv_rows == (["NAME", "Jan-25", "TOTAL"], [["X", 3, 3]])
    with pytest.raises(TableError):
        parse_table(b"a,b\n1,2\n", _spec(format="csv", header_contains="missing"))


def test_bundled_insights_carry_real_figures_and_their_source():
    found = insights.service_insights("mohesr-degree-recognition", {})
    assert (
        found[0]["headline"]["en"]
        == "73,019 applications to recognise a qualification from abroad in 2025"
    )
    assert "April (8,039)" in found[0]["detail"]["en"] and "ديسمبر" in found[0]["detail"]["ar"]
    assert len(found[0]["series"]) == 12
    assert {i["dataset_key"] for i in found} == {
        "mohesr-eservices-usage",
        "mofa-documents-attestation",
    }
    assert (
        insights.service_insights("uae-pass-account", {}) == []
    )  # no open dataset: nothing invented


def test_insights_are_personalised_with_the_profile():
    uaq = insights.service_insights("birth-registration", {"emirate": "umm_al_quwain"})[0]
    assert uaq["headline"]["en"] == "1,334 births were registered in Umm Al Quwain in 2024"
    assert "of the UAE's 106,915 births" in uaq["detail"]["en"]
    expat = insights.service_insights("newborn-residence-permit", {"emirate": "dubai"})[0]
    assert expat["headline"]["en"].startswith(
        "30,708 babies were born to expatriate families in Dubai"
    )
    whole = insights.service_insights("birth-registration", {})[0]
    assert "in the UAE in 2024" in whole["headline"]["en"]


def test_service_cards_show_insights_and_related_open_data(guest):
    guest.put(
        "/session/profile",
        {
            "emirate": "umm_al_quwain",
            "residency_status": None,
            "life_stage": None,
            "degree_issued_outside_uae": None,
        },
    )
    result = guest.discover("We just had a baby. What do we need to register?")
    card = next(c for c in result["results"] if c["service"]["id"] == "birth-registration")
    insight = card["insights"][0]
    assert insight["scope"] == "Umm Al Quwain" and insight["freshness"] == "current"
    assert insight["source"]["publisher"] == "Ministry of Health and Prevention"
    assert insight["source"]["url"].startswith("https://bayanat.ae/")
    assert insight["source"]["origin"] == "bundled" and insight["source"]["source_updated"]
    assert card["related_data"] and all(
        r["url"].startswith("https://") for r in card["related_data"]
    )


def _bayanat_transport(fail_downloads: bool) -> httpx.MockTransport:
    card = (
        '<a href="/en/Datasets/Dataset-info?id={id}"><div class="dataset-card"><h3 class="sub-title">{title}</h3>'
        '<p><img src="/image/icons/building-grey.svg"> {entity} </p><p>Last Updated Date 16/03/2026</p></div></a>'
    )
    cards = "".join(
        card.format(id=f"d{i}", title=s.title, entity=s.publisher)
        for i, s in enumerate(catalogue().datasets)
    )
    page = (
        "<html><h1>{title}</h1><p>Twitter</p><p>About.</p><p>Data and Resources</p>"
        '<div data-item="{{"id":"Res_ID_aaaaaaaaaaaaaaaaaaaa","nameEN":"Monthly e-services usage statistics-CSV","nameAR":"x","formatID":70006}}"></div></html>'
    )
    csv_body = "SERVICE NAME EN,SERVICE NAME AR,Jan-25,Feb-25,TOTAL\nRecognition of Qualifications issued Out side the UAE,x,10,30,40\n"

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/en/Datasets":
            return httpx.Response(
                200, text='<input name="__RequestVerificationToken" type="hidden" value="tok" />'
            )
        if path == "/DatasetsListing/GetDatasetsListing":
            return httpx.Response(
                200, json={"pagingDTO": {"totalCount": len(catalogue().datasets)}, "pv": cards}
            )
        if path.endswith("Dataset-info"):
            return httpx.Response(200, text=page.format(title="A dataset"))
        if path == "/api/DatasetResources/DownloadSingle":
            if fail_downloads:
                return httpx.Response(
                    503, text="<html>down</html>", headers={"content-type": "text/html"}
                )
            return httpx.Response(
                200, content=csv_body.encode(), headers={"content-type": "text/csv"}
            )
        return httpx.Response(404)

    return httpx.MockTransport(handler)


def _ajman_transport() -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        item = {
            "dataset_id": "companies-by-license-type",
            "metas": {
                "default": {
                    "title": "Companies by License Type",
                    "publisher": "Free Zones Authority",
                    "modified": "2025-01-02",
                }
            },
        }
        return httpx.Response(200, json={"total_count": 1, "results": [item]})

    return httpx.MockTransport(handler)


def test_sync_indexes_catalogues_refreshes_snapshots_and_keeps_copies_on_failure(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'sync.db'}")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        assert import_bundled(db) == len(catalogue().datasets)  # first start: shipped copies
        assert is_stale(db, 24)
        bayanat = Bayanat(
            5,
            httpx.Client(
                base_url="https://bayanat.ae", transport=_bayanat_transport(fail_downloads=False)
            ),
        )
        ajman = AjmanData(
            5, httpx.Client(base_url="https://data.ajman.ae", transport=_ajman_transport())
        )
        run = run_sync(db, bayanat, ajman)
        assert run.status == "partial"  # the fake portal only serves the MoHESR layout
        assert run.datasets_indexed == len(catalogue().datasets) + 1
        live = db.get(OdSnapshot, "mohesr-eservices-usage")
        assert live.origin == "live" and live.rows == [
            ["Recognition of Qualifications issued Out side the UAE", "x", 10, 30, 40]
        ]
        assert str(live.source_updated) == "2026-03-16"
        kept = db.get(OdSnapshot, "mohap-live-births")
        assert kept.origin == "bundled" and len(kept.rows) > 100  # failure keeps the previous copy
        assert any("kept the previous copy" in n for n in run.notes)
        assert not is_stale(db, 24)
        assert db.scalar(select(OdDataset).where(OdDataset.portal == "ajman")).theme == "economy"

        down = Bayanat(
            5,
            httpx.Client(
                base_url="https://bayanat.ae", transport=_bayanat_transport(fail_downloads=True)
            ),
        )
        again = run_sync(db, down, None, index=False)
        assert (
            again.snapshots_ok == 0
            and db.get(OdSnapshot, "mohesr-eservices-usage").origin == "live"
        )


def test_open_data_endpoints_and_health(client):
    summary = client.get("/api/v1/open-data").json()
    assert {p["portal"]: p["datasets_indexed"] > 3000 for p in summary["portals"]}["bayanat"]
    assert {c["source"]["key"] for c in summary["curated"]} == {d.key for d in catalogue().datasets}
    assert any("GetDatasetResource" in f for f in summary["findings"])
    moe = next(c for c in summary["curated"] if c["source"]["key"] == "moe-services-on-time")
    assert moe["freshness"] == "older" and moe["data_period"] == "2019"
    arabic = client.get("/api/v1/open-data", params={"locale": "ar"}).json()
    assert "بيانات" in arabic["findings"][0]
    found = client.get("/api/v1/open-data/search", params={"q": "golden visa"}).json()
    assert any("Golden" in d["title"] for d in found)
    assert client.get("/api/v1/open-data/search", params={"q": "x"}).status_code == 422
    health = client.get("/api/v1/health").json()["open_data"]
    assert health["datasets_indexed"] > 3000 and health["curated_snapshots"] == len(
        catalogue().datasets
    )


def test_navigation_gaps_are_anonymous_and_published(client, guest):
    from app.db.session import get_sessionmaker

    secret = "My passport number is A1234567 and I need my overseas degree recognized"
    discovery = guest.discover(secret)
    plan = guest.post(
        "/journeys",
        json={"discovery_id": discovery["id"], "service_ids": ["mohesr-degree-recognition"]},
    )
    assert plan.status_code == 201
    with get_sessionmaker()() as db:
        events = list(db.scalars(select(NavEvent)))
    assert {e.kind for e in events} >= {"search", "plan"}
    assert "A1234567" not in json.dumps([e.__dict__ for e in events], default=str)
    gaps = client.get("/api/v1/open-data/navigation-gaps").json()
    row = next(r for r in gaps["rows"] if r["topic"] == "education_qualification")
    assert row["searches"] >= 1 and row["plans"] >= 1 and row["median_seconds_to_plan"] is not None
    csv = client.get("/api/v1/open-data/navigation-gaps.csv")
    assert csv.headers["content-type"].startswith("text/csv")
    assert csv.text.splitlines()[0].startswith("week,topic,searches")


def test_the_agent_gets_citable_open_data_figures(client):
    model = RecordingModel()
    set_provider_override(model)
    Guest(client).discover(DEGREE_QUERY)
    facts = model.payloads[0]["OPEN_DATA"]
    mohesr = next(f for f in facts if f["service_id"] == "mohesr-degree-recognition")
    assert mohesr["fact"].startswith("73,019 applications") and mohesr["source_url"].startswith(
        "https://bayanat.ae/"
    )
    assert "OPEN_DATA holds official figures" in model.systems[0]
