from datetime import date
from typing import Literal

from pydantic import Field

from app.core.schemas import HttpsUrl, RequestModel, ResponseModel, UtcDateTime, VerificationStatus
from app.modules.sessions.schemas import ProfileField

Relevance = Literal["potentially_relevant", "more_information_needed", "criterion_mismatch"]
Readiness = Literal["ready", "prerequisites_needed", "unknown"]


class Source(ResponseModel):
    id: str
    title: str
    url: HttpsUrl | None
    publisher: str
    checked_at: UtcDateTime | None
    source_updated_at: date | None
    verification_status: VerificationStatus


class Requirement(ResponseModel):
    id: str
    text: str
    source_ids: list[str]


class Service(ResponseModel):
    id: str
    life_event_ids: list[str]
    title: str
    summary: str
    entity: str
    jurisdiction: str
    eligibility_criteria: list[Requirement]
    documents: list[Requirement]
    fee_text: str | None
    processing_time_text: str | None
    official_url: HttpsUrl | None
    support_url: HttpsUrl | None
    sources: list[Source]
    verification_status: VerificationStatus
    origin: Literal["catalog", "ai_web"] = Field(
        description="catalog = reviewed NaviNation record; ai_web = found by the AI agent on an "
        "official website during this session and not reviewed by NaviNation"
    )


class Reason(ResponseModel):
    text: str
    source_ids: list[str]


class Contact(ResponseModel):
    label: str
    phone: str = Field(description="As published by the entity")
    tel: str = Field(description="tel: link that dials from a UAE phone")
    email: str | None
    hours: str | None
    source_url: HttpsUrl
    source_title: str


class Center(ResponseModel):
    id: str
    name: str
    address: str | None
    lat: float
    lng: float
    note: str | None
    source: Literal["openstreetmap"] = "openstreetmap"


class Reach(ResponseModel):
    """How to reach a person for this service: published phone numbers and nearby centres."""

    contacts: list[Contact]
    centers: list[Center]
    map_query: str | None = Field(description="Google Maps search for this kind of centre")


class Location(RequestModel):
    """The person's position, shared from the browser for this request only (never stored)."""

    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)


class NearbyRequest(RequestModel):
    location: Location | None = None
    request: str | None = Field(
        default=None, max_length=500, description="Anything specific, e.g. 'open on Saturday'"
    )


class Nearby(ResponseModel):
    service_id: str
    message: str
    reach: Reach


class DataSource(ResponseModel):
    """Where an open-data figure comes from, so people (and judges) can check it."""

    key: str
    title: str
    publisher: str
    portal: Literal["bayanat", "ajman"]
    url: HttpsUrl
    source_updated: date | None = Field(description="The portal's own last-updated date")
    fetched_at: UtcDateTime = Field(description="When NaviNation last downloaded it")
    origin: Literal["live", "bundled"] = Field(
        description="live = synced from the portal; bundled = the reviewed copy shipped with the app"
    )


class InsightPoint(ResponseModel):
    label: str
    value: float


class Insight(ResponseModel):
    """A figure from government open data that helps plan this service."""

    id: str
    headline: str = Field(description="The whole fact as a sentence")
    label: str = Field(description="The fact without its number, to sit under a large value")
    detail: str | None
    value: float | None
    change: float | None = Field(
        description="Change vs compared_to: percent for counts, percentage points for percents"
    )
    compared_to: str | None
    unit: Literal["count", "percent"] | None
    period: str
    scope: str
    freshness: Literal["current", "older"]
    series: list[InsightPoint]
    highlight: int | None = Field(description="Index of the point to emphasise in the series")
    source: DataSource


class RelatedDataset(ResponseModel):
    title: str
    publisher: str
    portal: Literal["bayanat", "ajman"]
    theme: str | None
    url: HttpsUrl
    last_updated: date | None


class ServiceCard(ResponseModel):
    service: Service
    relevance: Relevance
    reasons: list[Reason] = Field(min_length=0)
    missing_profile_fields: list[ProfileField]
    readiness: Readiness
    authority_notice: str
    reach: Reach | None = None
    insights: list[Insight] = Field(
        description="Figures from government open data for this service"
    )
    related_data: list[RelatedDataset] = Field(description="Other open datasets on the same topic")
