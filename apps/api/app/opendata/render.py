"""Open-data insights and related datasets as API objects for a service card."""

from typing import Any

from app.modules.services import schemas
from app.opendata import index
from app.opendata.insights import freshness, service_insights, snapshots


def data_source(key: str) -> schemas.DataSource | None:
    snap = snapshots().get(key)
    if snap is None:
        return None
    return schemas.DataSource(
        key=snap.key,
        title=snap.title,
        publisher=snap.publisher,
        portal=snap.portal,  # type: ignore[arg-type]
        url=snap.url,
        source_updated=snap.source_updated,
        fetched_at=snap.fetched_at,
        origin=snap.origin,  # type: ignore[arg-type]
    )


def insights(service_id: str, profile: dict[str, Any], locale: str) -> list[schemas.Insight]:
    out = []
    for item in service_insights(service_id, profile):
        source = data_source(item["dataset_key"])
        if source is None:
            continue
        pick = lambda value: (value or {}).get(locale) or (value or {}).get("en")  # noqa: E731
        out.append(
            schemas.Insight(
                id=item["id"],
                headline=pick(item["headline"]) or "",
                label=pick(item["label"]) or "",
                change=item.get("change"),
                compared_to=item.get("compared_to"),
                detail=pick(item.get("detail")),
                value=item.get("value"),
                unit=item.get("unit"),
                period=item["period"],
                scope=pick(item["scope"]) or "",
                freshness=freshness(item["period"]),  # type: ignore[arg-type]
                series=[
                    schemas.InsightPoint(label=pick(p["label"]) or "", value=p["value"])
                    for p in item["series"]
                ],
                highlight=item.get("highlight"),
                source=source,
            )
        )
    return out


def related(service_id: str, title_en: str, origin: str) -> list[schemas.RelatedDataset]:
    """Catalog services use their reviewed topic searches; web-found ones search by title."""
    try:
        items = (
            index.related(service_id) if origin == "catalog" else index.search(title_en, limit=3)
        )
    except Exception:  # noqa: BLE001 - a missing or empty index must never break a card
        return []
    return [schemas.RelatedDataset(**item) for item in items if item["url"].startswith("https://")]
