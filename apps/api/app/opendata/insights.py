"""Service insights computed from government open data: real figures that help a person plan
(how busy a service is, when it is quieter, what is attested most, how many families go through
it in their emirate). Every insight carries the dataset it came from.

Insights are bilingual ({en, ar}) and personalised with the optional profile (emirate,
residency). Snapshots are read through a small cache that a sync or import invalidates.
"""

import logging
import re
import threading
import time
from collections import defaultdict
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from app.db.models import OdSnapshot
from app.db.session import get_sessionmaker
from app.opendata.tables import catalogue, norm

logger = logging.getLogger("navination.opendata")
CACHE_SECONDS = 300
MONTHS = {
    "jan": ("January", "يناير"),
    "feb": ("February", "فبراير"),
    "mar": ("March", "مارس"),
    "apr": ("April", "أبريل"),
    "may": ("May", "مايو"),
    "jun": ("June", "يونيو"),
    "jul": ("July", "يوليو"),
    "aug": ("August", "أغسطس"),
    "sep": ("September", "سبتمبر"),
    "oct": ("October", "أكتوبر"),
    "nov": ("November", "نوفمبر"),
    "dec": ("December", "ديسمبر"),
}
MONTH_KEYS = list(MONTHS)
EMIRATES = {
    "abu_dhabi": ("abudhabi", "Abu Dhabi", "أبوظبي"),
    "dubai": ("dubai", "Dubai", "دبي"),
    "sharjah": ("sharjah", "Sharjah", "الشارقة"),
    "ajman": ("ajman", "Ajman", "عجمان"),
    "umm_al_quwain": ("ummalquwain", "Umm Al Quwain", "أم القيوين"),
    "ras_al_khaimah": ("rasalkhaima", "Ras Al Khaimah", "رأس الخيمة"),
    "fujairah": ("fujairah", "Fujairah", "الفجيرة"),
}
UAE = ("UAE", "الإمارات")
DOCUMENTS_AR = {
    "educational certificates": "الشهادات الدراسية",
    "birth certificates": "شهادات الميلاد",
    "marriage contracts": "عقود الزواج",
}

_cache: dict[str, Any] = {"at": 0.0, "rows": {}}
_lock = threading.Lock()


def invalidate() -> None:
    with _lock:
        _cache["at"] = 0.0


def snapshots() -> dict[str, OdSnapshot]:
    with _lock:
        if time.monotonic() - _cache["at"] < CACHE_SECONDS:
            return _cache["rows"]
    try:
        with get_sessionmaker()() as db:
            rows = {row.key: row for row in db.scalars(select(OdSnapshot))}
            for row in rows.values():
                db.expunge(row)
    except SQLAlchemyError:
        logger.warning("open data snapshots unavailable (database not migrated?)")
        rows = {}
    with _lock:
        _cache.update(at=time.monotonic(), rows=rows)
    return rows


def _fmt(n: float) -> str:
    return f"{int(round(n)):,}"


def _pct(n: float) -> str:
    return f"{n:.0f}%" if abs(n) >= 10 else f"{n:.1f}%".replace(".0%", "%")


def _delta(now: float, before: float) -> float | None:
    return round((now - before) / before * 100, 1) if before else None


def _change(now: float, before: float) -> tuple[str, str] | None:
    if not before:
        return None
    delta = (now - before) / before * 100
    sign = "+" if delta >= 0 else "−"
    return f"{sign}{_pct(abs(delta))}", f"{sign}{_pct(abs(delta))}"


def _col(columns: list[str], *needles: str) -> int:
    return next(i for i, c in enumerate(columns) if all(n in norm(c) for n in needles))


def _insight(key: str, insight_id: str, **fields: Any) -> dict[str, Any]:
    return {"id": insight_id, "dataset_key": key, **fields}


# --------------------------------------------------------------------------- MoHESR e-services
def _mohesr(snap: OdSnapshot, service_id: str, profile: dict[str, Any]) -> list[dict[str, Any]]:
    cols, rows = snap.columns, snap.rows
    name = _col(cols, "service name en")
    month_cols = [(i, c) for i, c in enumerate(cols) if re.fullmatch(r"[a-z]{3}-\d{2}", norm(c))]
    row = next(
        (
            r
            for r in rows
            if "outside" in norm(r[name]).replace(" ", "") or "out side" in norm(r[name])
        ),
        None,
    )
    if row is None or not month_cols:
        return []
    values = [(norm(c)[:3], float(row[i] or 0)) for i, c in month_cols]
    year = "20" + norm(month_cols[-1][1])[-2:]
    total = sum(v for _, v in values)
    peak = max(values, key=lambda x: x[1])
    low = min(values, key=lambda x: x[1])
    all_total = sum(float(r[i] or 0) for r in rows for i, _ in month_cols)
    share = total / all_total * 100 if all_total else 0
    return [
        _insight(
            snap.key,
            "mohesr-recognition-volume",
            value=total,
            label={
                "en": f"applications to recognise a qualification from abroad in {year}",
                "ar": f"طلب اعتراف بمؤهل صادر من خارج الدولة في {year}",
            },
            change=None,
            compared_to=None,
            unit="count",
            period=year,
            scope={"en": "UAE", "ar": "الإمارات"},
            headline={
                "en": f"{_fmt(total)} applications to recognise a qualification from abroad in {year}",
                "ar": f"{_fmt(total)} طلب اعتراف بمؤهل صادر من خارج الدولة في {year}",
            },
            detail={
                "en": f"Busiest month: {MONTHS[peak[0]][0]} ({_fmt(peak[1])}). Quietest: "
                f"{MONTHS[low[0]][0]} ({_fmt(low[1])}). It was {_pct(share)} of all MoHESR e-service use.",
                "ar": f"أكثر الأشهر ازدحاماً: {MONTHS[peak[0]][1]} ({_fmt(peak[1])}). أهدأها: "
                f"{MONTHS[low[0]][1]} ({_fmt(low[1])}). شكّل {_pct(share)} من استخدام خدمات الوزارة الإلكترونية.",
            },
            series=[
                {"label": {"en": MONTHS[m][0][:3], "ar": MONTHS[m][1]}, "value": v}
                for m, v in values
            ],
            highlight=values.index(peak),
        )
    ]


# --------------------------------------------------------------------------- MoFA attestation
def _mofa(snap: OdSnapshot, service_id: str, profile: dict[str, Any]) -> list[dict[str, Any]]:
    cols, rows = snap.columns, snap.rows
    when, personal = 0, _col(cols, "personal affairs documents")
    abroad, top = _col(cols, "missions abroad"), _col(cols, "top 3", "personal")
    by_year: dict[str, list[list[Any]]] = defaultdict(list)
    for r in rows:
        if isinstance(r[when], str) and len(r[when]) >= 7:
            by_year[r[when][:4]].append(r)
    full = [y for y in sorted(by_year) if len(by_year[y]) >= 12]
    if not full:
        return []
    year = full[-1]
    prev = str(int(year) - 1)
    out: list[dict[str, Any]] = []
    latest = by_year[year]
    documents = [d.strip() for d in str(latest[-1][top] or "").split(";") if d.strip()]
    docs_en = ", ".join(d.split(" (")[0].lower() for d in documents)
    docs_ar = "، ".join(DOCUMENTS_AR.get(d.split(" (")[0].lower(), d) for d in documents)
    personal_total = sum(float(r[personal] or 0) for r in latest)
    change = _change(personal_total, sum(float(r[personal] or 0) for r in by_year.get(prev, [])))
    out.append(
        _insight(
            snap.key,
            "mofa-personal-documents",
            value=personal_total,
            label={
                "en": f"personal documents attested by MoFA in {year}",
                "ar": f"مستنداً شخصياً صدّقته وزارة الخارجية في {year}",
            },
            change=_delta(
                personal_total, sum(float(r[personal] or 0) for r in by_year.get(prev, []))
            ),
            compared_to=prev,
            unit="count",
            period=year,
            scope={"en": "UAE", "ar": "الإمارات"},
            headline={
                "en": f"{_fmt(personal_total)} personal documents attested by MoFA in {year}",
                "ar": f"{_fmt(personal_total)} مستنداً شخصياً صدّقته وزارة الخارجية في {year}",
            },
            detail={
                "en": f"Most attested: {docs_en}." + (f" {change[0]} on {prev}." if change else ""),
                "ar": f"الأكثر تصديقاً: {docs_ar}."
                + (f" {change[1]} مقارنة بعام {prev}." if change else ""),
            },
            series=[
                {
                    "label": {
                        "en": MONTHS[MONTH_KEYS[int(r[when][5:7]) - 1]][0][:3],
                        "ar": MONTHS[MONTH_KEYS[int(r[when][5:7]) - 1]][1],
                    },
                    "value": float(r[personal] or 0),
                }
                for r in latest
            ],
            highlight=None,
        )
    )
    if service_id == "mofa-attestation-abroad":
        abroad_total = sum(float(r[abroad] or 0) for r in latest)
        change = _change(abroad_total, sum(float(r[abroad] or 0) for r in by_year.get(prev, [])))
        busiest = max(latest, key=lambda r: float(r[abroad] or 0))
        month = MONTHS[MONTH_KEYS[int(busiest[when][5:7]) - 1]]
        out.insert(
            0,
            _insight(
                snap.key,
                "mofa-missions-abroad",
                value=abroad_total,
                label={
                    "en": f"attestation requests through UAE missions abroad in {year}",
                    "ar": f"طلب تصديق عبر بعثات الدولة في الخارج في {year}",
                },
                change=_delta(
                    abroad_total, sum(float(r[abroad] or 0) for r in by_year.get(prev, []))
                ),
                compared_to=prev,
                unit="count",
                period=year,
                scope={"en": "UAE missions abroad", "ar": "بعثات الدولة في الخارج"},
                headline={
                    "en": f"{_fmt(abroad_total)} attestation requests through UAE missions abroad in {year}",
                    "ar": f"{_fmt(abroad_total)} طلب تصديق عبر بعثات الدولة في الخارج في {year}",
                },
                detail={
                    "en": (f"{change[0]} on {prev}. " if change else "")
                    + f"Busiest month: {month[0]}.",
                    "ar": (f"{change[1]} مقارنة بعام {prev}. " if change else "")
                    + f"أكثر الأشهر ازدحاماً: {month[1]}.",
                },
                series=[
                    {
                        "label": {
                            "en": MONTHS[MONTH_KEYS[int(r[when][5:7]) - 1]][0][:3],
                            "ar": MONTHS[MONTH_KEYS[int(r[when][5:7]) - 1]][1],
                        },
                        "value": float(r[abroad] or 0),
                    }
                    for r in latest
                ],
                highlight=latest.index(busiest),
            ),
        )
    return out


# --------------------------------------------------------------------------- MOHAP births
def _births(snap: OdSnapshot, service_id: str, profile: dict[str, Any]) -> list[dict[str, Any]]:
    cols, rows = snap.columns, snap.rows
    y, e, nat, total = (
        _col(cols, "year"),
        _col(cols, "emirate"),
        _col(cols, "nationality"),
        _col(cols, "total"),
    )
    emirate = EMIRATES.get(profile.get("emirate") or "")
    group = {
        "mabrouk-ma-yak": "citizen",
        "newborn-residence-permit": "expat",
        "newborn-passport-embassy": "expat",
    }.get(service_id)

    def count(year: int, place: str | None, who: str | None) -> float:
        return sum(
            float(r[total] or 0)
            for r in rows
            if r[y] == year
            and (place is None or re.sub(r"[^a-z]", "", str(r[e]).lower()) == place)
            and (who is None or str(r[nat]).lower() == who)
        )

    years = sorted({r[y] for r in rows if isinstance(r[y], int)})
    if not years:
        return []
    year = years[-1]
    place = emirate[0] if emirate else None
    scope = {"en": emirate[1], "ar": emirate[2]} if emirate else {"en": UAE[0], "ar": UAE[1]}
    where = {"en": emirate[1] if emirate else "the UAE", "ar": scope["ar"]}
    value = count(year, place, group)
    if not value:
        return []
    change = _change(value, count(year - 1, place, group))
    whole = count(year, place, None)
    labels = {
        "citizen": (
            f"Emirati babies born in {where['en']} in {year}",
            f"طفلاً مواطناً وُلدوا في {where['ar']} عام {year}",
        ),
        "expat": (
            f"babies born to expatriate families in {where['en']} in {year}",
            f"طفلاً وُلدوا لأسر وافدة في {where['ar']} عام {year}",
        ),
        None: (
            f"births registered in {where['en']} in {year}",
            f"ولادة مسجلة في {where['ar']} عام {year}",
        ),
    }[group]
    if group == "citizen":
        headline = {
            "en": f"{_fmt(value)} Emirati babies were born in {where['en']} in {year}",
            "ar": f"وُلد {_fmt(value)} طفلاً مواطناً في {where['ar']} عام {year}",
        }
    elif group == "expat":
        headline = {
            "en": f"{_fmt(value)} babies were born to expatriate families in {where['en']} in {year}",
            "ar": f"وُلد {_fmt(value)} طفلاً لأسر وافدة في {where['ar']} عام {year}",
        }
    else:
        headline = {
            "en": f"{_fmt(value)} births were registered in {where['en']} in {year}",
            "ar": f"سُجّلت {_fmt(value)} ولادة في {where['ar']} عام {year}",
        }
    parts_en, parts_ar = [], []
    if change:
        parts_en.append(f"{change[0]} on {year - 1}.")
        parts_ar.append(f"{change[1]} مقارنة بعام {year - 1}.")
    if group and whole:
        parts_en.append(f"That is {_pct(value / whole * 100)} of all births there.")
        parts_ar.append(f"أي {_pct(value / whole * 100)} من جميع الولادات هناك.")
    elif emirate:
        uae = count(year, None, None)
        if uae:
            parts_en.append(f"{_pct(value / uae * 100)} of the UAE's {_fmt(uae)} births.")
            parts_ar.append(f"{_pct(value / uae * 100)} من إجمالي {_fmt(uae)} ولادة في الدولة.")
    recent = years[-10:]
    return [
        _insight(
            snap.key,
            f"births-{group or 'all'}",
            value=value,
            label={"en": labels[0], "ar": labels[1]},
            change=_delta(value, count(year - 1, place, group)),
            compared_to=str(year - 1),
            unit="count",
            period=str(year),
            scope=scope,
            headline=headline,
            detail={"en": " ".join(parts_en), "ar": " ".join(parts_ar)} if parts_en else None,
            series=[
                {"label": {"en": str(yr), "ar": str(yr)}, "value": count(yr, place, group)}
                for yr in recent
            ],
            highlight=len(recent) - 1,
        )
    ]


# --------------------------------------------------------------------------- MoE services on time
def _moe(snap: OdSnapshot, service_id: str, profile: dict[str, Any]) -> list[dict[str, Any]]:
    cols, rows = snap.columns, snap.rows
    y, name, pct = _col(cols, "year"), _col(cols, "service_name_en"), _col(cols, "percentage")
    points = sorted(
        (r[y], float(r[pct]) * (100 if float(r[pct]) <= 1 else 1))
        for r in rows
        if "equivalen" in norm(r[name]) and isinstance(r[y], int) and r[pct] is not None
    )
    if not points:
        return []
    year, value = points[-1]
    return [
        _insight(
            snap.key,
            "moe-equivalence-on-time",
            value=value,
            label={
                "en": f"of certificate-equivalence requests completed on time in {year}",
                "ar": f"من طلبات معادلة الشهادات أُنجزت في الوقت المحدد عام {year}",
            },
            change=round(value - points[-2][1], 1) if len(points) > 1 else None,
            compared_to=str(points[-2][0]) if len(points) > 1 else None,
            unit="percent",
            period=str(year),
            scope={"en": "Ministry of Education", "ar": "وزارة التربية والتعليم"},
            headline={
                "en": f"{_pct(value)} of certificate-equivalence requests were completed on time in {year}",
                "ar": f"أُنجز {_pct(value)} من طلبات معادلة الشهادات في الوقت المحدد عام {year}",
            },
            detail={
                "en": "Measured at the Ministry of Education's customer happiness centre.",
                "ar": "حسب قياس مركز سعادة المتعاملين في وزارة التربية والتعليم.",
            },
            series=[{"label": {"en": str(yr), "ar": str(yr)}, "value": v} for yr, v in points],
            highlight=len(points) - 1,
        )
    ]


EXTRACTORS = {
    "mohesr-eservices-usage": _mohesr,
    "mofa-documents-attestation": _mofa,
    "mohap-live-births": _births,
    "moe-services-on-time": _moe,
}


def freshness(period: str, now: datetime | None = None) -> str:
    """Older figures stay visible but are labelled: data more than three years old is 'older'."""
    year = int(re.sub(r"\D", "", period)[:4] or 0)
    current = (now or datetime.now(UTC)).year
    return "current" if year >= current - 3 else "older"


def service_insights(service_id: str, profile: dict[str, Any]) -> list[dict[str, Any]]:
    """All insights for a catalog service, most useful first. Never raises: bad data is skipped."""
    rows = snapshots()
    out: list[dict[str, Any]] = []
    for spec in catalogue().for_service(service_id):
        snap = rows.get(spec.key)
        extractor = EXTRACTORS.get(spec.key)
        if snap is None or extractor is None:
            continue
        try:
            out += extractor(snap, service_id, profile)
        except (StopIteration, ValueError, TypeError, IndexError, KeyError):
            continue  # a changed file layout must not break a service card
    return out[:3]
