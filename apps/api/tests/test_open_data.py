"""Open-data clients (bayanat.ae, data.ajman.ae) against mocked HTTP: no network access."""

import httpx
import pytest

from app.agent.ajman import AjmanData, AjmanError
from app.agent.bayanat import Bayanat, BayanatError, parse_cards, parse_dataset_page, preview_csv

CARD = """
<a href="/en/Datasets/Dataset-info?id=abc123" target="_self">
  <div class="dataset-card"><h3 class="sub-title">Marriage contracts &amp; divorce</h3>
  <p><img src="/image/icons/building-grey.svg">
     Ministry of Justice
  </p><p>Last Updated Date 20/05/2026</p></div></a>
"""

DATASET_PAGE = """<html><body><h1>Births by emirate</h1>
<p>Twitter</p><p>Number of births per emirate and year.</p><p>Data and Resources</p>
<p><img src="/image/icons/building-grey.svg"> FCSC </p>
<div class="accordion-item"><input type="checkbox"
 data-item="{"id":"Res_ID_aaaaaaaaaaaaaaaaaaaa","nameEN":"Births \\u0026 deaths","nameAR":"x","formatID":70006,"fileURL":"/File/Get/1"}"></div>
</body></html>"""


def test_parse_cards():
    [card] = parse_cards(CARD)
    assert card.title == "Marriage contracts & divorce"
    assert card.entity == "Ministry of Justice"
    assert card.last_updated == "20/05/2026"
    assert card.url == "https://bayanat.ae/en/Datasets/Dataset-info?id=abc123"


def test_parse_dataset_page():
    detail = parse_dataset_page("https://bayanat.ae/en/Datasets/Dataset-info?id=x", DATASET_PAGE)
    assert detail.title == "Births by emirate"
    assert detail.description == "Number of births per emirate and year."
    assert [(r.resource_id, r.name, r.format) for r in detail.resources] == [
        ("Res_ID_aaaaaaaaaaaaaaaaaaaa", "Births & deaths", "CSV")
    ]


def test_preview_csv():
    preview = preview_csv(b"Year,Emirate,Value\n2024,Dubai,10\n2024,Ajman,3\n")
    assert preview["columns"] == ["Year", "Emirate", "Value"]
    assert preview["row_count"] == 2
    assert preview["rows"][1] == ["2024", "Ajman", "3"]


def _bayanat(handler) -> Bayanat:  # type: ignore[no-untyped-def]
    return Bayanat(
        5, httpx.Client(base_url="https://bayanat.ae", transport=httpx.MockTransport(handler))
    )


def test_bayanat_search_replays_token():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(
                200,
                text='<input name="__RequestVerificationToken" type="hidden" value="tok" />',
            )
        seen["body"] = request.content.decode()
        return httpx.Response(200, json={"pagingDTO": {"totalCount": 1}, "pv": CARD})

    total, datasets = _bayanat(handler).search("marriage")
    assert total == 1 and datasets[0].entity == "Ministry of Justice"
    assert "__RequestVerificationToken=tok" in seen["body"]
    assert "searchText=marriage" in seen["body"]


def test_bayanat_resource_rejects_bad_ids_and_html():
    client = _bayanat(
        lambda r: httpx.Response(
            200, text="<html>404</html>", headers={"content-type": "text/html"}
        )
    )
    with pytest.raises(BayanatError):
        client.resource("../../etc")
    with pytest.raises(BayanatError):
        client.resource("Res_ID_aaaaaaaaaaaaaaaaaaaa")
    with pytest.raises(BayanatError):
        client.dataset("https://example.com/x")


def _ajman(handler) -> AjmanData:  # type: ignore[no-untyped-def]
    return AjmanData(
        5, httpx.Client(base_url="https://data.ajman.ae", transport=httpx.MockTransport(handler))
    )


def test_ajman_search_and_records():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/records"):
            return httpx.Response(200, json={"total_count": 2, "results": [{"a": 1}, {"a": 2}]})
        assert request.url.params["where"] == 'search("trade license")'
        return httpx.Response(
            200,
            json={
                "total_count": 1,
                "results": [
                    {
                        "dataset_id": "companies-by-license-type",
                        "metas": {
                            "default": {
                                "title": "Companies by License Type",
                                "publisher": "Free Zones Authority",
                                "description": "<p>Companies &amp; licences</p>",
                                "records_count": 2,
                            }
                        },
                    }
                ],
            },
        )

    client = _ajman(handler)
    total, [dataset] = client.search("trade license")
    assert total == 1 and dataset.description == "Companies & licences"
    assert dataset.url == "https://data.ajman.ae/explore/dataset/companies-by-license-type/"
    assert client.records("companies-by-license-type")["total_records"] == 2
    with pytest.raises(AjmanError):
        client.records("../secret")
