"""Search over the locally mirrored open-data catalogues (Bayanat and Ajman Data)."""

import math
import re
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.exc import SQLAlchemyError

from app.db.models import OdDataset
from app.db.session import get_sessionmaker
from app.opendata.tables import catalogue

_STOP = {"the", "of", "and", "in", "by", "for", "to", "a", "an", "on", "at", "uae", "data"}


def _terms(query: str) -> list[str]:
    words = [w for w in re.findall(r"[\w-]+", query.lower()) if len(w) > 1 and w not in _STOP]
    # Light stemming so "births" finds "birth" and "centres" finds "centre".
    return [w[:-1] if len(w) > 4 and w.endswith("s") else w for w in words][:8]


def search(query: str, *, portal: str | None = None, limit: int = 8) -> list[dict[str, Any]]:
    """Datasets ranked by how many query words they contain (title words count double)."""
    terms = _terms(query)
    if not terms:
        return []
    try:
        with get_sessionmaker()() as db:
            stmt = select(OdDataset).where(or_(*(OdDataset.search_text.contains(t) for t in terms)))
            if portal:
                stmt = stmt.where(OdDataset.portal == portal)
            candidates = list(db.scalars(stmt.limit(400)))
    except SQLAlchemyError:
        return []  # no local index yet: callers fall back to the live portal
    scored = []
    for d in candidates:
        title = d.title.lower()
        hits = sum(1 for t in terms if t in d.search_text)
        if hits < max(1, math.ceil(len(terms) * 0.6)):
            continue
        score = hits + sum(1 for t in terms if t in title) + (0.5 if d.last_updated else 0)
        scored.append((score, d.last_updated.isoformat() if d.last_updated else "", d))
    scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return [as_dict(d) for _, _, d in scored[:limit]]


def as_dict(d: OdDataset) -> dict[str, Any]:
    return {
        "title": d.title,
        "publisher": d.entity,
        "portal": d.portal,
        "theme": d.theme,
        "url": d.url,
        "last_updated": d.last_updated,
    }


def related(service_id: str, limit: int = 3) -> list[dict[str, Any]]:
    """Other open datasets about a catalog service's topic (excluding the curated ones)."""
    cat = catalogue()
    curated = {norm_title(d.title) for d in cat.for_service(service_id)}
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for query in cat.related.get(service_id, []):
        for item in search(query, limit=6):
            key = norm_title(item["title"])
            if key in curated or key in seen:
                continue
            seen.add(key)
            out.append(item)
            if len(out) >= limit:
                return out
    return out


def norm_title(title: str) -> str:
    return " ".join(title.lower().split())
