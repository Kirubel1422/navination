"""Read-only access to bayanat.ae, the UAE federal open-data portal (run by FCSC).

- Search: Bayanat has no public search API; its dataset listing page posts to an internal endpoint
  that returns rendered dataset cards. We replay that request (session cookie + anti-forgery token
  taken from the listing page) and parse the cards into title / entity / last update / URL.
- Dataset pages: parsed for description and resources (name, format, resource id).
- Resource data: the documented REST endpoint `/api/DatasetResources/GetDatasetResource?resourceID=`
  returned an empty body for every resource GUID we could find (checked 2026-10-29), so we use
  `/api/DatasetResources/DownloadSingle`, the endpoint behind the portal's own Download button.
  CSV resources are previewed (header, row count, first rows); other formats are listed only.
"""

import contextlib
import csv
import html
import io
import json
import re
import threading
import time
from dataclasses import dataclass

import httpx

from app.agent.web import USER_AGENT, html_to_text

BASE_URL = "https://bayanat.ae"
TOKEN_TTL_SECONDS = 20 * 60
CACHE_TTL_SECONDS = 6 * 3600
MAX_RESULTS = 8
MAX_PREVIEW_ROWS = 15
MAX_RESOURCE_BYTES = 3_000_000
DATASET_PREFIX = BASE_URL + "/en/Datasets/Dataset-info?id="

_TOKEN = re.compile(r'name="__RequestVerificationToken" type="hidden" value="([^"]+)"')
_CARD_LINK = re.compile(r'href="(/en/Datasets/Dataset-info\?id=[^"]+)"')
_CARD_TITLE = re.compile(r'class="sub-title">(.*?)</h3>', re.S)
_CARD_ENTITY = re.compile(r'building-grey\.svg">(.*?)</p>', re.S)
_CARD_UPDATED = re.compile(r"Last Updated Date\s*([0-9/]+)")
_RESOURCE = re.compile(
    r'data-item="\{"id":"([^"]+)","nameEN":"((?:[^"\\]|\\.)*)".*?"formatID":(\d+)'
)
_H1 = re.compile(r"<h1[^>]*>(.*?)</h1>", re.S)
_RESOURCE_ID = re.compile(r"^[A-Za-z0-9_-]{20,80}$")
# Bayanat format ids seen on dataset pages.
_FORMATS = {70002: "XLSX", 70006: "CSV"}


class BayanatError(Exception):
    pass


@dataclass(frozen=True)
class Dataset:
    title: str
    entity: str
    last_updated: str
    url: str


def _clean(fragment: str) -> str:
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", fragment)).split())


def parse_cards(rendered: str) -> list[Dataset]:
    datasets: list[Dataset] = []
    seen: set[str] = set()
    for match in _CARD_LINK.finditer(rendered):  # each card follows its dataset link
        url = BASE_URL + html.unescape(match.group(1))
        if url in seen:
            continue
        seen.add(url)
        card = rendered[match.end() : match.end() + 6000]
        title = _CARD_TITLE.search(card)
        entity = _CARD_ENTITY.search(card)
        updated = _CARD_UPDATED.search(card)
        if title is None:
            continue
        datasets.append(
            Dataset(
                title=_clean(title.group(1)),
                entity=_clean(entity.group(1)) if entity else "",
                last_updated=updated.group(1) if updated else "",
                url=url,
            )
        )
    return datasets


@dataclass(frozen=True)
class Resource:
    resource_id: str
    name: str
    format: str


@dataclass(frozen=True)
class DatasetDetail:
    url: str
    title: str
    entity: str
    description: str
    resources: list[Resource]


def parse_dataset_page(url: str, page: str) -> DatasetDetail:
    _, text = html_to_text(page)
    start, end = text.find("Twitter"), text.find("Data and Resources")
    description = text[start + len("Twitter") : end].strip() if 0 <= start < end else ""
    title = _H1.search(page)
    entity = _CARD_ENTITY.search(page)
    resources = []
    for rid, name, fmt in _RESOURCE.findall(page):
        with contextlib.suppress(ValueError):  # decode \u escapes in the embedded JSON
            name = json.loads(f'"{name}"')
        resources.append(Resource(rid, name, _FORMATS.get(int(fmt), "other")))
    return DatasetDetail(
        url=url,
        title=_clean(title.group(1)) if title else "",
        entity=_clean(entity.group(1)) if entity else "",
        description=description[:1500],
        resources=resources[:20],
    )


def preview_csv(raw: bytes) -> dict[str, object]:
    text = raw.decode("utf-8-sig", errors="replace")
    rows = list(csv.reader(io.StringIO(text)))
    rows = [[" ".join(cell.split()) for cell in row] for row in rows if any(row)]
    if not rows:
        return {"format": "CSV", "columns": [], "row_count": 0, "rows": []}
    return {
        "format": "CSV",
        "columns": rows[0],
        "row_count": len(rows) - 1,
        "rows": rows[1 : 1 + MAX_PREVIEW_ROWS],
    }


class Bayanat:
    def __init__(self, timeout_seconds: float, client: httpx.Client | None = None) -> None:
        self.client = client or httpx.Client(
            base_url=BASE_URL,
            timeout=timeout_seconds,
            follow_redirects=True,
            headers={"User-Agent": USER_AGENT},
        )
        self._token: tuple[float, str] | None = None
        self._cache: dict[str, tuple[float, tuple[int, list[Dataset]]]] = {}
        self._lock = threading.Lock()

    def _fresh_token(self, force: bool = False) -> str:
        if not force and self._token and time.monotonic() - self._token[0] < TOKEN_TTL_SECONDS:
            return self._token[1]
        try:
            page = self.client.get("/en/Datasets")  # also sets the anti-forgery cookie
        except httpx.HTTPError as exc:
            raise BayanatError(f"Could not reach bayanat.ae: {type(exc).__name__}") from exc
        match = _TOKEN.search(page.text)
        if page.status_code >= 400 or match is None:
            raise BayanatError("bayanat.ae search is unavailable right now.")
        self._token = (time.monotonic(), html.unescape(match.group(1)))
        return self._token[1]

    def _post(
        self, query: str, token: str, page: int = 1, size: int = MAX_RESULTS
    ) -> httpx.Response:
        return self.client.post(
            "/DatasetsListing/GetDatasetsListing",
            headers={"X-Requested-With": "XMLHttpRequest", "Referer": BASE_URL + "/en/Datasets"},
            data={
                "searchText": query,
                "lang": "en",
                "SortingBy": "newest",
                "pagingDTO[CurrentPageNumber]": str(page),
                "pagingDTO[PageCount]": str(size),
                "pagingDTO[IsFilterUpdated]": "true",
                "__RequestVerificationToken": token,
            },
        )

    def search(self, query: str) -> tuple[int, list[Dataset]]:
        """Returns (total matching datasets, first page of datasets)."""
        query = " ".join(query.split())[:120]
        key = query.lower()
        with self._lock:
            cached = self._cache.get(key)
            if cached and time.monotonic() - cached[0] < CACHE_TTL_SECONDS:
                return cached[1]
            try:
                response = self._post(query, self._fresh_token())
                if response.status_code >= 400 or "json" not in response.headers.get(
                    "content-type", ""
                ):
                    response = self._post(query, self._fresh_token(force=True))
                data = response.json()
            except (httpx.HTTPError, ValueError) as exc:
                raise BayanatError(f"bayanat.ae search failed: {type(exc).__name__}") from exc
            total = int((data.get("pagingDTO") or {}).get("totalCount") or 0)
            result = (total, parse_cards(str(data.get("pv") or ""))[:MAX_RESULTS])
            self._cache[key] = (time.monotonic(), result)
            return result

    def catalogue_page(self, page: int, size: int = 500) -> tuple[int, list[Dataset]]:
        """One page of the whole catalogue (newest first), for the local index sync."""
        try:
            response = self._post("", self._fresh_token(), page, size)
            if response.status_code >= 400 or "json" not in response.headers.get(
                "content-type", ""
            ):
                response = self._post("", self._fresh_token(force=True), page, size)
            data = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise BayanatError(
                f"bayanat.ae catalogue page {page} failed: {type(exc).__name__}"
            ) from exc
        total = int((data.get("pagingDTO") or {}).get("totalCount") or 0)
        return total, parse_cards(str(data.get("pv") or ""))

    def download(self, resource_id: str) -> tuple[str, bytes]:
        """Raw bytes of a resource via the portal's own Download button endpoint."""
        if not _RESOURCE_ID.match(resource_id):
            raise BayanatError("Unknown resource_id; use one from get_bayanat_dataset.")
        try:
            response = self.client.get(
                "/api/DatasetResources/DownloadSingle",
                params={"resourceID": resource_id, "fileName": "resource"},
            )
        except httpx.HTTPError as exc:
            raise BayanatError(f"Could not reach bayanat.ae: {type(exc).__name__}") from exc
        content_type = response.headers.get("content-type", "")
        if response.status_code >= 400 or "html" in content_type:
            raise BayanatError("This resource could not be downloaded from bayanat.ae.")
        return content_type, response.content[:MAX_RESOURCE_BYTES]

    def dataset(self, url: str) -> DatasetDetail:
        if not url.startswith(DATASET_PREFIX):
            raise BayanatError(f"Not a bayanat dataset URL; expected {DATASET_PREFIX}<id>.")
        try:
            response = self.client.get(url.removeprefix(BASE_URL))
        except httpx.HTTPError as exc:
            raise BayanatError(f"Could not reach bayanat.ae: {type(exc).__name__}") from exc
        detail = parse_dataset_page(url, response.text)
        if response.status_code >= 400 or not detail.title or "404" in detail.title:
            raise BayanatError("This bayanat dataset page was not found.")
        return detail

    def resource(self, resource_id: str) -> dict[str, object]:
        content_type, content = self.download(resource_id)
        if "csv" in content_type or content_type.startswith("text/"):
            return preview_csv(content)
        return {
            "format": content_type or "unknown",
            "note": "Only CSV resources can be previewed here; open the dataset page to download.",
        }


_instance: Bayanat | None = None


def get_bayanat(timeout_seconds: float) -> Bayanat:
    global _instance
    if _instance is None:
        _instance = Bayanat(timeout_seconds)
    return _instance
