from typing import Annotated, Literal

from pydantic import StringConstraints

from app.core.schemas import HttpsUrl, RequestModel, ResponseModel, UtcDateTime


class HandoffRequest(RequestModel):
    step_id: Annotated[str, StringConstraints(min_length=1, max_length=80)]
    kind: Literal["official", "support"]


class Handoff(ResponseModel):
    id: str
    kind: Literal["official", "support"]
    service_id: str
    url: HttpsUrl
    label: str
    created_at: UtcDateTime
