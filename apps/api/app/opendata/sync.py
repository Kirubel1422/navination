"""Keeps NaviNation's open data current and available.

- Index: the full Bayanat (federal) and Ajman Data catalogues are mirrored into `od_datasets`, so
  dataset search is fast, works when a portal is slow or down, and does not scrape on every user
  request.
- Snapshots: the curated datasets in datasets.yaml are downloaded, parsed and stored with their
  provenance (portal, publisher, update date, fetch time, checksum).
- Bundled copies: a reviewed copy of every snapshot ships with the code (bundled/*.json), so
  insights work on first start and survive portal outages; a live sync replaces them.
- Every run is logged in `od_sync_runs`; freshness is reported by /health and /open-data.
"""

import gzip
import hashlib
import json
import logging
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session as DbSession

from app.agent.ajman import AjmanData, AjmanError
from app.agent.bayanat import Bayanat, BayanatError
from app.db.models import OdDataset, OdSnapshot, OdSyncRun
from app.opendata import insights
from app.opendata.tables import DatasetSpec, TableError, catalogue, norm, parse_table, pick_resource

logger = logging.getLogger("navination.opendata")
BUNDLED_DIR = Path(__file__).with_name("bundled")
PAGE_SIZE = 500
MAX_PAGES = 40

# Rough themes for browsing the index; matched on title and publisher (first match wins).
THEMES: list[tuple[str, tuple[str, ...]]] = [
    ("health", ("health", "hospital", "birth", "medical", "patient", "disease", "vaccin", "mohap")),
    (
        "education",
        ("education", "student", "school", "universit", "graduat", "academic", "college"),
    ),
    ("family", ("marriage", "divorce", "family", "child", "population", "household")),
    ("government", ("attestation", "e-services", "services", "transactions", "customer", "court")),
    ("economy", ("trade", "econom", "labour", "labor", "employment", "license", "investment")),
    ("transport", ("traffic", "transport", "vehicle", "road", "aviation", "port")),
    ("environment", ("environment", "climate", "water", "energy", "agricultur", "food")),
]


def theme_of(title: str, entity: str) -> str | None:
    text = f"{title} {entity}".lower()
    return next((name for name, words in THEMES if any(w in text for w in words)), None)


def _now() -> datetime:
    return datetime.now(UTC).replace(microsecond=0)


def _day(text: str | None) -> date | None:
    if not text:
        return None
    for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(text[:10], fmt).date()
        except ValueError:
            continue
    return None


def _dataset_id(portal: str, entity: str, title: str) -> str:
    # Portal ids are not stable (Bayanat encrypts them per page view): key on entity + title.
    digest = hashlib.sha1(f"{entity.lower()}|{title.lower()}".encode()).hexdigest()[:20]
    return f"{portal}:{digest}"


def _upsert(db: DbSession, rows: dict[str, dict[str, Any]], portal: str) -> int:
    existing = {d.id: d for d in db.scalars(select(OdDataset).where(OdDataset.portal == portal))}
    for dataset_id, values in rows.items():
        row = existing.get(dataset_id)
        if row is None:
            db.add(OdDataset(id=dataset_id, **values))
        else:
            for key, value in values.items():
                setattr(row, key, value)
    stale = [i for i in existing if i not in rows]
    if stale:
        db.execute(delete(OdDataset).where(OdDataset.id.in_(stale)))
    return len(rows)


def index_bayanat(db: DbSession, bayanat: Bayanat) -> int:
    now = _now()
    rows: dict[str, dict[str, Any]] = {}
    total, page = None, 1
    while page <= MAX_PAGES:
        total_count, cards = bayanat.catalogue_page(page, PAGE_SIZE)
        total = total_count if total is None else total
        for card in cards:
            dataset_id = _dataset_id("bayanat", card.entity, card.title)
            rows[dataset_id] = {
                "portal": "bayanat",
                "title": card.title,
                "entity": card.entity,
                "theme": theme_of(card.title, card.entity),
                "last_updated": _day(card.last_updated),
                "url": card.url,
                "description": None,
                "search_text": f"{card.title} {card.entity}".lower(),
                "synced_at": now,
            }
        if not cards or page * PAGE_SIZE >= (total or 0):
            break
        page += 1
    if not rows:
        raise BayanatError("bayanat.ae returned an empty catalogue")
    return _upsert(db, rows, "bayanat")


def index_ajman(db: DbSession, ajman: AjmanData) -> int:
    now = _now()
    rows: dict[str, dict[str, Any]] = {}
    for item in ajman.catalogue():
        dataset_id = _dataset_id("ajman", item.publisher, item.title)
        rows[dataset_id] = {
            "portal": "ajman",
            "title": item.title,
            "entity": item.publisher or "Ajman Government",
            "theme": theme_of(item.title, item.publisher),
            "last_updated": _day(item.modified),
            "url": item.url,
            "description": item.description or None,
            "search_text": f"{item.title} {item.publisher} {item.description}".lower(),
            "synced_at": now,
        }
    if not rows:
        raise AjmanError("data.ajman.ae returned an empty catalogue")
    return _upsert(db, rows, "ajman")


def _store_snapshot(db: DbSession, spec: DatasetSpec, values: dict[str, Any]) -> None:
    row = db.get(OdSnapshot, spec.key)
    if row is None:
        db.add(OdSnapshot(key=spec.key, **values))
    else:
        for key, value in values.items():
            setattr(row, key, value)


def snapshot_values(
    spec: DatasetSpec,
    columns: list[str],
    rows: list[list[Any]],
    *,
    resource_name: str,
    origin: str,
    source_updated: date | None,
    fetched_at: datetime,
) -> dict[str, Any]:
    checksum = hashlib.sha256(json.dumps([columns, rows], default=str).encode()).hexdigest()
    return {
        "title": spec.title,
        "publisher": spec.publisher,
        "portal": spec.portal,
        "url": spec.url,
        "resource_name": resource_name,
        "source_updated": source_updated,
        "fetched_at": fetched_at,
        "checksum": checksum,
        "columns": columns,
        "rows": rows,
        "origin": origin,
    }


def snapshot_live(db: DbSession, spec: DatasetSpec, bayanat: Bayanat) -> None:
    detail = bayanat.dataset(spec.url)
    resource = pick_resource(spec, detail.resources)
    _, content = bayanat.download(resource.resource_id)
    columns, rows = parse_table(content, spec)
    # The portal's own "last updated" date, from the catalogue index (matched on the title).
    wanted = norm(spec.title)
    candidates = db.scalars(
        select(OdDataset)
        .where(OdDataset.portal == spec.portal, OdDataset.title.ilike(f"%{spec.title.split()[0]}%"))
        .order_by(OdDataset.last_updated.desc())
    )
    indexed = next((d for d in candidates if norm(d.title) == wanted), None)
    _store_snapshot(
        db,
        spec,
        snapshot_values(
            spec,
            columns,
            rows,
            resource_name=resource.name,
            origin="live",
            source_updated=indexed.last_updated if indexed else None,
            fetched_at=_now(),
        ),
    )


INDEX_FILE = "catalogue-index.json.gz"


def _import_index(db: DbSession) -> int:
    """Load the shipped catalogue index when the local index is empty (first start, offline)."""
    path = BUNDLED_DIR / INDEX_FILE
    if not path.exists() or index_count(db) > 0:
        return 0
    data = json.loads(gzip.decompress(path.read_bytes()).decode("utf-8"))
    synced_at = datetime.fromisoformat(data["synced_at"])
    for item in data["datasets"]:
        db.add(
            OdDataset(
                id=item["id"],
                portal=item["portal"],
                title=item["title"],
                entity=item["entity"],
                theme=item.get("theme"),
                last_updated=_day(item.get("last_updated")),
                url=item["url"],
                description=item.get("description"),
                search_text=" ".join(
                    filter(None, (item["title"], item["entity"], item.get("description")))
                ).lower(),
                synced_at=synced_at,
            )
        )
    return len(data["datasets"])


def import_bundled(db: DbSession, *, replace: bool = False) -> int:
    """Load the shipped snapshots (and catalogue index) where nothing newer is stored yet."""
    _import_index(db)
    imported = 0
    for spec in catalogue().datasets:
        path = BUNDLED_DIR / f"{spec.key}.json"
        if not path.exists():
            continue
        if db.get(OdSnapshot, spec.key) is not None and not replace:
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        _store_snapshot(
            db,
            spec,
            snapshot_values(
                spec,
                data["columns"],
                data["rows"],
                resource_name=data["resource_name"],
                origin="bundled",
                source_updated=_day(data.get("source_updated")),
                fetched_at=datetime.fromisoformat(data["fetched_at"]),
            ),
        )
        imported += 1
    db.commit()
    insights.invalidate()
    return imported


def export_bundled(db: DbSession) -> list[Path]:
    """Write the current snapshots as the shipped copies (run after a successful live sync)."""
    BUNDLED_DIR.mkdir(exist_ok=True)
    written = []
    for row in db.scalars(select(OdSnapshot)):
        path = BUNDLED_DIR / f"{row.key}.json"
        payload = {
            "key": row.key,
            "title": row.title,
            "publisher": row.publisher,
            "url": row.url,
            "resource_name": row.resource_name,
            "source_updated": row.source_updated.isoformat() if row.source_updated else None,
            "fetched_at": row.fetched_at.isoformat(),
            "columns": row.columns,
            "rows": row.rows,
        }
        path.write_text(
            json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8"
        )
        written.append(path)
    datasets = [
        {
            "id": d.id,
            "portal": d.portal,
            "title": d.title,
            "entity": d.entity,
            "theme": d.theme,
            "last_updated": d.last_updated.isoformat() if d.last_updated else None,
            "url": d.url,
            "description": d.description,
        }
        for d in db.scalars(select(OdDataset).order_by(OdDataset.id))
    ]
    if datasets:
        index_path = BUNDLED_DIR / INDEX_FILE
        payload = {"synced_at": _now().isoformat(), "datasets": datasets}
        index_path.write_bytes(
            gzip.compress(json.dumps(payload, ensure_ascii=False).encode("utf-8"), mtime=0)
        )
        written.append(index_path)
    return written


def run_sync(
    db: DbSession,
    bayanat: Bayanat,
    ajman: AjmanData | None,
    *,
    index: bool = True,
    snapshots: bool = True,
) -> OdSyncRun:
    run = OdSyncRun(started_at=_now(), status="running", notes=[])
    db.add(run)
    db.commit()
    notes: list[str] = []
    indexed = ok = failed = 0
    if index:
        for name, job in (
            ("bayanat", lambda: index_bayanat(db, bayanat)),
            ("ajman", lambda: index_ajman(db, ajman) if ajman else 0),
        ):
            try:
                count = job()
                db.commit()
                indexed += count
                notes.append(f"{name}: {count} datasets indexed")
            except (BayanatError, AjmanError) as exc:
                db.rollback()
                notes.append(f"{name}: index not refreshed ({exc})")
    if snapshots:
        for spec in catalogue().datasets:
            try:
                snapshot_live(db, spec, bayanat)
                db.commit()
                ok += 1
            except (BayanatError, TableError) as exc:
                db.rollback()
                failed += 1
                notes.append(f"{spec.key}: kept the previous copy ({exc})")
    run.finished_at = _now()
    run.datasets_indexed = indexed
    run.snapshots_ok = ok
    run.snapshots_failed = failed
    run.notes = notes
    run.status = (
        "ok"
        if not failed and (indexed or not index)
        else ("partial" if indexed or ok else "failed")
    )
    db.add(run)
    db.commit()
    insights.invalidate()
    logger.info("open data sync %s: %s", run.status, "; ".join(notes))
    return run


def last_success(db: DbSession) -> OdSyncRun | None:
    return db.scalar(
        select(OdSyncRun)
        .where(OdSyncRun.status.in_(("ok", "partial")))
        .order_by(OdSyncRun.id.desc())
    )


def is_stale(db: DbSession, max_age_hours: float) -> bool:
    run = last_success(db)
    if run is None or run.finished_at is None:
        return True
    finished = run.finished_at if run.finished_at.tzinfo else run.finished_at.replace(tzinfo=UTC)
    return _now() - finished > timedelta(hours=max_age_hours)


def index_count(db: DbSession, portal: str | None = None) -> int:
    query = select(func.count()).select_from(OdDataset)
    if portal:
        query = query.where(OdDataset.portal == portal)
    return int(db.scalar(query) or 0)
