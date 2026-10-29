"""Read-only access to official UAE government websites for the agent.

- Only HTTPS URLs on the configured official domains (and their subdomains) are fetched.
  Redirects are followed manually and every hop is re-checked, so a redirect can never lead
  the backend to another host.
- Responses are size-limited, reduced to plain text and cached in-process for a few hours.
- Optional web search (Tavily or Brave) is restricted to the same domains. Search results are
  leads only: the agent must fetch a page before it may cite it or link to it.
"""

import re
import threading
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from html.parser import HTMLParser
from typing import Protocol
from urllib.parse import urljoin, urlparse

import httpx

from app.core.config import Settings

MAX_BYTES = 1_500_000
MAX_TEXT_CHARS = 9_000
# Longer text kept for checking contact details, which often sit in page footers.
MAX_FULL_TEXT_CHARS = 60_000
MAX_LINKS = 40
MAX_REDIRECTS = 3
CACHE_TTL_SECONDS = 6 * 3600
USER_AGENT = "NaviNation/1.1 (prototype service navigator; contact via project README)"


class WebError(Exception):
    pass


@dataclass(frozen=True)
class Page:
    url: str
    title: str
    text: str
    fetched_at: datetime
    links: tuple[tuple[str, str], ...] = ()  # (anchor text, absolute URL) on official domains
    full_text: str = ""


@dataclass(frozen=True)
class SearchHit:
    title: str
    url: str
    snippet: str


def host_of(url: str) -> str:
    return (urlparse(url).hostname or "").lower()


def is_official_url(url: str, domains: list[str]) -> bool:
    parsed = urlparse(url)
    if (
        parsed.scheme != "https"
        or parsed.username
        or parsed.password
        or parsed.port not in (None, 443)
    ):
        return False
    host = (parsed.hostname or "").lower().rstrip(".")
    return any(host == d or host.endswith("." + d) for d in (x.lower().strip(".") for x in domains))


class _TextExtractor(HTMLParser):
    SKIP = {"script", "style", "noscript", "svg", "template", "iframe"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.title_parts: list[str] = []
        self._skip = 0
        self._in_title = False

    def handle_starttag(self, tag: str, attrs: list) -> None:  # type: ignore[type-arg]
        if tag in self.SKIP:
            self._skip += 1
        elif tag == "title":
            self._in_title = True
        elif tag in ("p", "li", "h1", "h2", "h3", "h4", "tr", "br", "div", "section"):
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in self.SKIP and self._skip:
            self._skip -= 1
        elif tag == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        if self._skip:
            return
        if self._in_title:
            self.title_parts.append(data)
        else:
            self.parts.append(data)


class _LinkExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[tuple[str, str]] = []
        self._href: str | None = None
        self._text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list) -> None:  # type: ignore[type-arg]
        if tag == "a":
            self._href = dict(attrs).get("href")
            self._text = []

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._href:
            self.links.append((" ".join("".join(self._text).split()), self._href))
            self._href = None

    def handle_data(self, data: str) -> None:
        if self._href:
            self._text.append(data)


def extract_links(html: str, base_url: str, domains: list[str]) -> tuple[tuple[str, str], ...]:
    """Official-domain links with readable anchor text, so the agent can navigate instead of
    guessing URLs."""
    parser = _LinkExtractor()
    parser.feed(html)
    seen: set[str] = set()
    out: list[tuple[str, str]] = []
    for text, href in parser.links:
        url = urljoin(base_url, href).split("#")[0]
        if len(text) < 3 or url in seen or url == base_url or not is_official_url(url, domains):
            continue
        seen.add(url)
        out.append((text[:80], url))
        if len(out) >= MAX_LINKS:
            break
    return tuple(out)


def html_to_text(html: str) -> tuple[str, str]:
    parser = _TextExtractor()
    parser.feed(html)
    title = " ".join("".join(parser.title_parts).split())
    text = "".join(parser.parts)
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n", text).strip()
    return title, text


class SearchBackend(Protocol):
    def search(self, query: str, domains: list[str]) -> list[SearchHit]: ...


class TavilySearch:
    """Tavily Search API (https://docs.tavily.com). Requires WEB_SEARCH_API_KEY."""

    def __init__(self, api_key: str, client: httpx.Client) -> None:
        self.api_key = api_key
        self.client = client

    def search(self, query: str, domains: list[str]) -> list[SearchHit]:
        response = self.client.post(
            "https://api.tavily.com/search",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={"query": query, "include_domains": domains, "max_results": 6},
        )
        response.raise_for_status()
        return [
            SearchHit(r.get("title", ""), r.get("url", ""), (r.get("content") or "")[:500])
            for r in response.json().get("results", [])
        ]


class BraveSearch:
    """Brave Search API (https://api-dashboard.search.brave.com). Requires WEB_SEARCH_API_KEY."""

    def __init__(self, api_key: str, client: httpx.Client) -> None:
        self.api_key = api_key
        self.client = client

    def search(self, query: str, domains: list[str]) -> list[SearchHit]:
        sites = " OR ".join(f"site:{d}" for d in domains)
        response = self.client.get(
            "https://api.search.brave.com/res/v1/web/search",
            headers={"X-Subscription-Token": self.api_key, "Accept": "application/json"},
            params={"q": f"{query} ({sites})", "count": 8},
        )
        response.raise_for_status()
        results = response.json().get("web", {}).get("results", [])
        return [
            SearchHit(r.get("title", ""), r.get("url", ""), (r.get("description") or "")[:500])
            for r in results
        ]


class OfficialWeb:
    def __init__(
        self,
        settings: Settings,
        client: httpx.Client | None = None,
        search_backend: SearchBackend | None = None,
    ) -> None:
        self.domains = list(settings.official_domains)
        self.fetch_enabled = settings.web_fetch_enabled
        self.client = client or httpx.Client(
            timeout=settings.web_fetch_timeout_seconds,
            follow_redirects=False,
            headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"},
        )
        self.search_backend = search_backend
        if search_backend is None and settings.web_search_configured:
            key = settings.web_search_api_key or ""
            if settings.web_search_provider == "tavily":
                self.search_backend = TavilySearch(key, self.client)
            elif settings.web_search_provider == "brave":
                self.search_backend = BraveSearch(key, self.client)
        self._cache: dict[str, tuple[float, Page]] = {}
        self._lock = threading.Lock()

    @property
    def search_available(self) -> bool:
        return self.search_backend is not None

    def is_official(self, url: str) -> bool:
        return is_official_url(url, self.domains)

    def fetch(self, url: str) -> Page:
        if not self.fetch_enabled:
            raise WebError("Fetching official pages is disabled on this server.")
        if not self.is_official(url):
            raise WebError(
                f"Only HTTPS pages on official domains can be read: {', '.join(self.domains)}"
            )
        with self._lock:
            cached = self._cache.get(url)
        if cached and time.monotonic() - cached[0] < CACHE_TTL_SECONDS:
            return cached[1]

        current = url
        for _ in range(MAX_REDIRECTS + 1):
            try:
                response = self.client.get(current)
            except httpx.HTTPError as exc:
                raise WebError(f"Could not reach {host_of(current)}: {type(exc).__name__}") from exc
            if response.is_redirect:
                target = urljoin(current, response.headers.get("location", ""))
                if not self.is_official(target):
                    raise WebError("The page redirected outside the official domains.")
                current = target
                continue
            break
        else:
            raise WebError("Too many redirects.")

        if response.status_code >= 400:
            raise WebError(f"{host_of(current)} returned HTTP {response.status_code}.")
        content_type = response.headers.get("content-type", "")
        if "html" not in content_type and "text" not in content_type:
            raise WebError(f"Unsupported content type: {content_type or 'unknown'}")
        body = response.content[:MAX_BYTES].decode(response.encoding or "utf-8", errors="replace")
        title, text = html_to_text(body) if "html" in content_type else ("", body)
        if len(text) < 40:
            raise WebError("The page has no readable text (it may need JavaScript).")
        page = Page(
            url=current,
            title=title or host_of(current),
            text=text[:MAX_TEXT_CHARS],
            full_text=text[:MAX_FULL_TEXT_CHARS],
            fetched_at=datetime.now(UTC).replace(microsecond=0),
            links=extract_links(body, current, self.domains) if "html" in content_type else (),
        )
        with self._lock:
            self._cache[url] = (time.monotonic(), page)
            self._cache[current] = (time.monotonic(), page)
        return page

    def search(self, query: str) -> list[SearchHit]:
        if self.search_backend is None:
            raise WebError("Web search is not configured on this server; use fetch_official_page.")
        try:
            hits = self.search_backend.search(query, self.domains)
        except httpx.HTTPError as exc:
            raise WebError(f"Search failed: {type(exc).__name__}") from exc
        return [hit for hit in hits if self.is_official(hit.url)][:6]


_instance: OfficialWeb | None = None
_override: OfficialWeb | None = None


def get_official_web(settings: Settings) -> OfficialWeb:
    global _instance
    if _override is not None:
        return _override
    if _instance is None:
        _instance = OfficialWeb(settings)
    return _instance


def set_official_web_override(web: OfficialWeb | None) -> None:
    """Test hook."""
    global _override
    _override = web
