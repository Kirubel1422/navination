"""Public, read-only open-data endpoints: which government data NaviNation uses, how fresh it is,
a search over the mirrored catalogues, and the navigation-gaps dataset NaviNation publishes."""

import csv
import io
from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Query
from fastapi.responses import Response
from sqlalchemy import select

from app.core.config import get_settings
from app.db.models import OdSyncRun
from app.db.session import get_sessionmaker
from app.knowledge.repository import get_knowledge
from app.modules.opendata import schemas
from app.modules.services.schemas import RelatedDataset
from app.opendata import index, navigation, sync
from app.opendata.insights import freshness, service_insights, snapshots
from app.opendata.render import data_source
from app.opendata.tables import catalogue

router = APIRouter(tags=["open data"])
LICENCE = "UAE Open Data: free to reuse with attribution to NaviNation"

FINDINGS = {
    "en": [
        "Bayanat has no public search API, so NaviNation mirrors the whole catalogue once a day (8 requests) instead of scraping on each search.",
        "Bayanat's documented endpoint GetDatasetResource?resourceID={GUID} returned an empty body for every resource we tried; we read files through the portal's own download endpoint.",
        "Bayanat re-encrypts dataset and resource ids on every page view, so datasets are keyed on publisher and title.",
        "The playbook's Ajman API host (api.ajman.ae) does not resolve; the same Explore API v2.1 is served at data.ajman.ae.",
        "No open dataset of service-centre locations was found; nearby centres come from OpenStreetMap until one is published.",
        "Data we would request: UAE PASS sign-up volumes and Emirates ID processing times, which are not on Bayanat.",
    ],
    "ar": [
        "لا توفر منصة «بيانات» واجهة بحث عامة، لذلك ينسخ NaviNation الفهرس كاملاً مرة يومياً (8 طلبات) بدلاً من الاستخراج مع كل بحث.",
        "أعادت الواجهة الموثقة GetDatasetResource?resourceID={GUID} نتيجة فارغة لكل مورد جربناه، لذلك نقرأ الملفات عبر نقطة التنزيل الخاصة بالمنصة.",
        "تعيد منصة «بيانات» تشفير معرّفات المجموعات والموارد مع كل زيارة، لذلك نميّز المجموعات بالجهة الناشرة والعنوان.",
        "عنوان واجهة عجمان في الدليل (api.ajman.ae) غير متاح؛ وتعمل الواجهة نفسها Explore API v2.1 على data.ajman.ae.",
        "لم نعثر على مجموعة بيانات مفتوحة لمواقع مراكز الخدمة؛ لذلك تأتي المراكز القريبة من OpenStreetMap إلى أن تُنشر.",
        "بيانات نود طلبها: أعداد التسجيل في الهوية الرقمية وأوقات إنجاز الهوية الإماراتية، وهي غير منشورة في «بيانات».",
    ],
}


def _period(key: str, services: list[str]) -> str | None:
    for service_id in services:
        for item in service_insights(service_id, {}):
            if item["dataset_key"] == key:
                return item["period"]
    return None


@router.get("/open-data", response_model=schemas.OpenDataSummary)
def summary(locale: Literal["en", "ar"] = "en") -> schemas.OpenDataSummary:
    settings = get_settings()
    with get_sessionmaker()() as db:
        bayanat_count = sync.index_count(db, "bayanat")
        ajman_count = sync.index_count(db, "ajman")
        last = db.scalars(select(OdSyncRun).order_by(OdSyncRun.id.desc()).limit(1)).first()
        stale = sync.is_stale(db, settings.open_data_max_age_hours)
        last_status = (
            schemas.SyncStatus(
                status=last.status,
                started_at=last.started_at,
                finished_at=last.finished_at,
                datasets_indexed=last.datasets_indexed,
                snapshots_ok=last.snapshots_ok,
                snapshots_failed=last.snapshots_failed,
                notes=list(last.notes or []),
            )
            if last
            else None
        )
    with get_sessionmaker()() as db:
        kb = get_knowledge(db)
    curated = []
    for spec in catalogue().datasets:
        source = data_source(spec.key)
        if source is None:
            continue
        snap = snapshots()[spec.key]
        period = _period(spec.key, spec.services)
        curated.append(
            schemas.CuratedDataset(
                source=source,
                rows=len(snap.rows),
                columns=list(snap.columns),
                services=spec.services,
                service_titles=[
                    kb.services[s].title[locale] for s in spec.services if s in kb.services
                ],
                data_period=period,
                freshness=freshness(period) if period else "older",  # type: ignore[arg-type]
            )
        )
    return schemas.OpenDataSummary(
        portals=[
            schemas.PortalStatus(
                portal="bayanat",
                name="Bayanat: UAE federal open data portal (FCSC)",
                url="https://bayanat.ae",
                access="Daily catalogue mirror; dataset files via the portal's download endpoint",
                datasets_indexed=bayanat_count,
            ),
            schemas.PortalStatus(
                portal="ajman",
                name="Ajman Data (Department of Digital Ajman)",
                url="https://data.ajman.ae",
                access="Opendatasoft Explore API v2.1 (public, no key)",
                datasets_indexed=ajman_count,
            ),
        ],
        curated=curated,
        last_sync=last_status,
        stale=stale,
        findings=FINDINGS[locale],
        navigation_dataset_path="/api/v1/open-data/navigation-gaps.csv",
    )


@router.get("/open-data/search", response_model=list[RelatedDataset])
def search(
    q: Annotated[str, Query(min_length=2, max_length=120)],
    portal: Literal["bayanat", "ajman"] | None = None,
) -> list[RelatedDataset]:
    return [RelatedDataset(**item) for item in index.search(q, portal=portal, limit=20)]


def _gaps(days: int) -> schemas.NavigationGaps:
    with get_sessionmaker()() as db:
        rows = navigation.gaps(db, days)
    return schemas.NavigationGaps(
        generated_at=datetime.now(UTC).replace(microsecond=0),
        days=days,
        licence=LICENCE,
        rows=[schemas.NavigationGap(**row) for row in rows],
    )


@router.get("/open-data/navigation-gaps", response_model=schemas.NavigationGaps)
def navigation_gaps(days: Annotated[int, Query(ge=1, le=365)] = 90) -> schemas.NavigationGaps:
    return _gaps(days)


@router.get(
    "/open-data/navigation-gaps.csv",
    response_class=Response,
    responses={200: {"content": {"text/csv": {}}, "description": "The same rows as CSV"}},
)
def navigation_gaps_csv(days: Annotated[int, Query(ge=1, le=365)] = 90) -> Response:
    data = _gaps(days)
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    fields = list(schemas.NavigationGap.model_fields)
    writer.writerow(fields)
    for row in data.rows:
        writer.writerow([getattr(row, f) if getattr(row, f) is not None else "" for f in fields])
    return Response(
        buffer.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="navination-navigation-gaps.csv"'},
    )
