from typing import Literal

from pydantic import StrictBool

from app.core.schemas import Locale, RequestModel, ResponseModel, UtcDateTime

Emirate = Literal[
    "abu_dhabi", "dubai", "sharjah", "ajman", "umm_al_quwain", "ras_al_khaimah", "fujairah"
]
ResidencyStatus = Literal["citizen", "resident", "visitor"]
LifeStage = Literal["student", "worker", "parent", "other"]
ProfileField = Literal["emirate", "residency_status", "life_stage", "degree_issued_outside_uae"]


class Profile(ResponseModel):
    emirate: Emirate | None
    residency_status: ResidencyStatus | None
    life_stage: LifeStage | None
    degree_issued_outside_uae: bool | None


class ProfileRequest(RequestModel):
    """All four fields are required; null means unknown (distinct from false)."""

    emirate: Emirate | None
    residency_status: ResidencyStatus | None
    life_stage: LifeStage | None
    degree_issued_outside_uae: StrictBool | None


class Session(ResponseModel):
    id: str
    locale: Locale
    expires_at: UtcDateTime
    context_revision: int
    profile: Profile


class CreateSessionRequest(RequestModel):
    locale: Locale


class CreateSessionResponse(ResponseModel):
    session: Session
    access_token: str


class UpdateSessionRequest(RequestModel):
    locale: Locale
