"""Shared transport-schema base classes and the error envelope."""

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, PlainSerializer, StringConstraints, WithJsonSchema

from app.core.timeutil import iso

Locale = Literal["en", "ar"]
VerificationStatus = Literal["verified", "needs_review", "demo"]
UtcDateTime = Annotated[
    datetime,
    PlainSerializer(lambda v: iso(v), return_type=str),
    WithJsonSchema({"type": "string", "format": "date-time"}),
]
HttpsUrl = Annotated[
    str, WithJsonSchema({"type": "string", "format": "uri", "pattern": "^https://"})
]
ShortId = Annotated[str, StringConstraints(min_length=1, max_length=80)]


class RequestModel(BaseModel):
    """Request bodies reject unexpected fields and never coerce types."""

    model_config = ConfigDict(extra="forbid", strict=True)


class ResponseModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ErrorDetail(ResponseModel):
    field: str | None
    message: str


class ErrorBody(ResponseModel):
    code: str
    message: str
    details: list[ErrorDetail]
    request_id: str


class ErrorEnvelope(ResponseModel):
    error: ErrorBody


def error_responses(*codes: int) -> dict[int | str, dict]:
    descriptions = {
        401: "Missing, invalid or expired session",
        404: "Not found (or owned by another session)",
        409: "Conflict: stale context, prerequisites, message ID or handoff unavailable",
        422: "Validation error",
        429: "Rate limited",
        503: "Temporarily unavailable",
    }
    return {
        code: {"model": ErrorEnvelope, "description": descriptions.get(code, "Error")}
        for code in codes
    }
