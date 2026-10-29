from datetime import date
from typing import Literal

from pydantic import Field

from app.core.schemas import HttpsUrl, ResponseModel, UtcDateTime
from app.modules.services.schemas import DataSource, RelatedDataset

__all__ = ["RelatedDataset"]


class PortalStatus(ResponseModel):
    portal: Literal["bayanat", "ajman"]
    name: str
    url: HttpsUrl
    access: str = Field(description="How NaviNation reads this portal")
    datasets_indexed: int


class CuratedDataset(ResponseModel):
    source: DataSource
    rows: int
    columns: list[str]
    services: list[str] = Field(description="Catalog services whose insights use this dataset")
    service_titles: list[str]
    data_period: str | None = Field(description="Latest period covered by the data")
    freshness: Literal["current", "older"]


class SyncStatus(ResponseModel):
    status: str
    started_at: UtcDateTime
    finished_at: UtcDateTime | None
    datasets_indexed: int
    snapshots_ok: int
    snapshots_failed: int
    notes: list[str]


class OpenDataSummary(ResponseModel):
    portals: list[PortalStatus]
    curated: list[CuratedDataset]
    last_sync: SyncStatus | None
    stale: bool = Field(
        description="True when no successful sync happened within the refresh window"
    )
    findings: list[str] = Field(
        description="What we learned integrating the portals (shared with FCSC)"
    )
    navigation_dataset_path: str


class NavigationGap(ResponseModel):
    week: date
    topic: str
    searches: int
    ready: int
    needs_clarification: int
    no_match: int
    plans: int
    median_seconds_to_plan: int | None


class NavigationGaps(ResponseModel):
    """Anonymous navigation outcomes: what people look for and where guidance fails."""

    generated_at: UtcDateTime
    days: int
    licence: str
    rows: list[NavigationGap]
