"""Read-only access to Ajman Data (data.ajman.ae), the Department of Digital Ajman's open-data
portal, through its public Opendatasoft Explore API v2.1 (no key needed).

The HackArena playbook names `api.ajman.ae/v2.1/datasets`; that host does not resolve, and the
same API is served at data.ajman.ae/api/explore/v2.1 (checked 2026-10-29).
"""

import html
import re
import threading
import time
from dataclasses import dataclass
from typing import Any

import httpx

from app.agent.web import USER_AGENT

BASE_URL = "https://data.ajman.ae"
API = "/api/explore/v2.1"
CACHE_TTL_SECONDS = 6 * 3600
MAX_RESULTS = 8
MAX_RECORDS = 15
_DATASET_ID = re.compile(r"^[a-z0-9_-]{1,120}$")


class AjmanError(Exception):
    pass


@dataclass(frozen=True)
class AjmanDataset:
    dataset_id: str
    title: str
    publisher: str
    description: str
    records_count: int
    modified: str
    url: str


def dataset_url(dataset_id: str) -> str:
    return f"{BASE_URL}/explore/dataset/{dataset_id}/"


def _plain(fragment: str | None) -> str:
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", fragment or "")).split())


def _quote(text: str) -> str:
    return '"' + text.replace("\\", " ").replace('"', " ") + '"'


class AjmanData:
    def __init__(self, timeout_seconds: float, client: httpx.Client | None = None) -> None:
        self.client = client or httpx.Client(
            base_url=BASE_URL,
            timeout=timeout_seconds,
            follow_redirects=False,
            headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
        )
        self._cache: dict[str, tuple[float, Any]] = {}
        self._lock = threading.Lock()

    def _get(self, path: str, params: dict[str, Any]) -> Any:
        key = path + repr(sorted(params.items()))
        with self._lock:
            cached = self._cache.get(key)
        if cached and time.monotonic() - cached[0] < CACHE_TTL_SECONDS:
            return cached[1]
        try:
            response = self.client.get(API + path, params=params)
        except httpx.HTTPError as exc:
            raise AjmanError(f"Could not reach data.ajman.ae: {type(exc).__name__}") from exc
        if response.status_code == 404:
            raise AjmanError("Unknown Ajman dataset_id; use one from search_ajman_datasets.")
        if response.status_code >= 400:
            raise AjmanError(f"data.ajman.ae returned HTTP {response.status_code}.")
        try:
            data = response.json()
        except ValueError as exc:
            raise AjmanError("data.ajman.ae returned an unreadable response.") from exc
        with self._lock:
            self._cache[key] = (time.monotonic(), data)
        return data

    def search(self, query: str) -> tuple[int, list[AjmanDataset]]:
        query = " ".join(query.split())[:120]
        data = self._get(
            "/catalog/datasets",
            {"where": f"search({_quote(query)})", "limit": MAX_RESULTS},
        )
        datasets = []
        for item in data.get("results", []):
            meta = (item.get("metas") or {}).get("default") or {}
            dataset_id = str(item.get("dataset_id", ""))
            datasets.append(
                AjmanDataset(
                    dataset_id=dataset_id,
                    title=_plain(meta.get("title")),
                    publisher=_plain(meta.get("publisher")),
                    description=_plain(meta.get("description"))[:400],
                    records_count=int(meta.get("records_count") or 0),
                    modified=str(meta.get("modified") or "")[:10],
                    url=dataset_url(dataset_id),
                )
            )
        return int(data.get("total_count") or 0), datasets

    def catalogue(self, page_size: int = 100, max_pages: int = 20) -> list[AjmanDataset]:
        """Every dataset on Ajman Data, for the local index sync (bypasses the request cache)."""
        datasets: list[AjmanDataset] = []
        for page in range(max_pages):
            try:
                response = self.client.get(
                    API + "/catalog/datasets",
                    params={"limit": page_size, "offset": page * page_size},
                )
                response.raise_for_status()
                data = response.json()
            except (httpx.HTTPError, ValueError) as exc:
                raise AjmanError(f"data.ajman.ae catalogue failed: {type(exc).__name__}") from exc
            for item in data.get("results", []):
                meta = (item.get("metas") or {}).get("default") or {}
                dataset_id = str(item.get("dataset_id", ""))
                datasets.append(
                    AjmanDataset(
                        dataset_id=dataset_id,
                        title=_plain(meta.get("title")),
                        publisher=_plain(meta.get("publisher")),
                        description=_plain(meta.get("description"))[:400],
                        records_count=int(meta.get("records_count") or 0),
                        modified=str(meta.get("modified") or "")[:10],
                        url=dataset_url(dataset_id),
                    )
                )
            if len(datasets) >= int(data.get("total_count") or 0) or not data.get("results"):
                break
        return datasets

    def records(self, dataset_id: str, query: str = "") -> dict[str, Any]:
        if not _DATASET_ID.match(dataset_id):
            raise AjmanError("Unknown Ajman dataset_id; use one from search_ajman_datasets.")
        params: dict[str, Any] = {"limit": MAX_RECORDS}
        if query.strip():
            params["where"] = f"search({_quote(' '.join(query.split())[:120])})"
        data = self._get(f"/catalog/datasets/{dataset_id}/records", params)
        return {
            "dataset_id": dataset_id,
            "url": dataset_url(dataset_id),
            "total_records": int(data.get("total_count") or 0),
            "records": data.get("results", [])[:MAX_RECORDS],
        }


_instance: AjmanData | None = None


def get_ajman(timeout_seconds: float) -> AjmanData:
    global _instance
    if _instance is None:
        _instance = AjmanData(timeout_seconds)
    return _instance
