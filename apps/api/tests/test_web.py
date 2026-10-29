import httpx
import pytest

from app.agent.web import WebError, html_to_text, is_official_url
from tests.fakes import fake_web, html

DOMAINS = ["u.ae", "gov.ae", "tamm.abudhabi"]


@pytest.mark.parametrize(
    ("url", "ok"),
    [
        ("https://u.ae/en/x", True),
        ("https://www.mohesr.gov.ae/en", True),
        ("https://tamm.abudhabi/x", True),
        ("http://u.ae/en", False),
        ("https://evil-u.ae/x", False),
        ("https://u.ae.evil.com/x", False),
        ("https://gov.ae.example.org/", False),
        ("https://user:pass@u.ae/", False),
        ("https://u.ae:8443/", False),
        ("javascript:alert(1)", False),
    ],
)
def test_official_domain_allow_list(url, ok):
    assert is_official_url(url, DOMAINS) is ok


def test_html_to_text_drops_scripts_and_keeps_title():
    title, text = html_to_text(
        "<html><title> A  page </title><script>x()</script><p>Hello</p><li>World</li></html>"
    )
    assert title == "A page"
    assert "x()" not in text and "Hello" in text and "World" in text


def test_fetch_reads_official_pages_and_blocks_others():
    web = fake_web(
        {
            "https://u.ae/a": html(
                "Golden visa", "The golden visa is a long-term residence visa for eligible people."
            )
        }
    )
    page = web.fetch("https://u.ae/a")
    assert page.title == "Golden visa" and "long-term" in page.text and "evil" not in page.text
    with pytest.raises(WebError, match="official domains"):
        web.fetch("https://example.com/")
    with pytest.raises(WebError, match="404"):
        web.fetch("https://u.ae/missing")


def test_redirect_off_domain_is_refused():
    web = fake_web(
        {
            "https://u.ae/r": (302, "", {"location": "https://evil.example/steal"}),
            "https://u.ae/ok": (301, "", {"location": "/final"}),
            "https://u.ae/final": html(
                "Final", "Final official page text that is long enough to read."
            ),
        }
    )
    with pytest.raises(WebError, match="outside the official domains"):
        web.fetch("https://u.ae/r")
    assert web.fetch("https://u.ae/ok").url == "https://u.ae/final"


def test_search_results_are_filtered_to_official_domains():
    web = fake_web(
        {},
        search=[
            {"title": "Official", "url": "https://u.ae/en/golden-visa", "content": "..."},
            {"title": "Blog", "url": "https://blog.example.com/golden", "content": "..."},
        ],
    )
    hits = web.search("golden visa")
    assert [h.url for h in hits] == ["https://u.ae/en/golden-visa"]


def test_search_without_configuration_is_an_explicit_error():
    web = fake_web({})
    assert web.search_available is False
    with pytest.raises(WebError, match="not configured"):
        web.search("anything")


def test_network_failures_become_web_errors():
    from app.agent.web import OfficialWeb
    from app.core.config import get_settings

    def boom(request):  # type: ignore[no-untyped-def]
        raise httpx.ConnectError("down", request=request)

    web = OfficialWeb(
        get_settings().model_copy(update={"web_fetch_enabled": True}),
        client=httpx.Client(transport=httpx.MockTransport(boom)),
    )
    with pytest.raises(WebError, match="Could not reach"):
        web.fetch("https://u.ae/x")
