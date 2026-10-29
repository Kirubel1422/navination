import uuid
from typing import Annotated, Literal

from pydantic import Field, StringConstraints, field_validator

from app.core.schemas import RequestModel, ResponseModel, UtcDateTime
from app.modules.discovery.schemas import AgentStep
from app.modules.services.schemas import Location, Reach, Source

MessageText = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4000)
]


class CoachMessage(ResponseModel):
    id: str
    role: Literal["user", "assistant"]
    content: str
    step_id: str | None
    citations: list[Source]
    reach: Reach | None = Field(default=None, description="Phone contacts / nearby centres")
    created_at: UtcDateTime


class SuggestedAction(ResponseModel):
    type: Literal["view_step", "open_official", "open_support"]
    step_id: str | None
    service_id: str | None


class CoachTurn(ResponseModel):
    user_message: CoachMessage
    assistant_message: CoachMessage
    mode: Literal["ai"]
    grounding_status: Literal["grounded", "insufficient_evidence"]
    suggested_actions: list[SuggestedAction]
    notices: list[str]
    agent_steps: list[AgentStep]


class CoachRequest(RequestModel):
    client_message_id: Annotated[
        str, Field(min_length=36, max_length=36, json_schema_extra={"format": "uuid"})
    ]
    message: MessageText
    step_id: Annotated[str, StringConstraints(min_length=1, max_length=80)] | None
    location: Location | None = Field(
        default=None, description="Shared by the person for nearby centres; used, never stored"
    )

    @field_validator("client_message_id")
    @classmethod
    def _uuid(cls, value: str) -> str:
        try:
            return str(uuid.UUID(value))
        except ValueError as exc:
            raise ValueError("client_message_id must be a UUID") from exc


class MessageList(ResponseModel):
    items: list[CoachMessage]
