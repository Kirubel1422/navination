from typing import Annotated, Literal

from pydantic import Field, StringConstraints, model_validator

from app.core.schemas import RequestModel, ResponseModel, UtcDateTime
from app.modules.discovery.schemas import AgentStep
from app.modules.services.schemas import ServiceCard
from app.modules.sessions.schemas import ProfileField

IdText = Annotated[str, StringConstraints(min_length=1, max_length=80)]
Progress = Literal["not_started", "in_progress", "completed"]
DocumentStatus = Literal["unknown", "have", "missing"]


class Dependency(ResponseModel):
    from_step_id: str
    to_step_id: str
    kind: Literal["required", "recommended"]
    explanation: str
    source_ids: list[str]


class DocumentProgress(ResponseModel):
    document_id: str
    status: DocumentStatus


class ChecklistItem(ResponseModel):
    """A preparation item written by the AI planner (or copied from a reviewed record)."""

    id: str
    text: str
    source_ids: list[str]
    ai_generated: bool


class Stage(ResponseModel):
    order_group: int = Field(ge=0)
    title: str
    description: str


class JourneyStep(ResponseModel):
    id: str
    title: str
    instructions: str
    checklist: list[ChecklistItem]
    service_card: ServiceCard
    order_group: int = Field(ge=0)
    prerequisite_step_ids: list[str]
    document_progress: list[DocumentProgress]
    progress: Progress
    availability: Literal["ready", "blocked", "review_needed"]
    blocker_step_ids: list[str]
    notes: list[str]
    tailored_by: list[ProfileField] = Field(
        description="Profile answers that shaped this step (from the reviewed catalog)"
    )
    tailored_note: str | None = Field(description="Catalog guidance for the person's answer")


class PersonalizationEffect(ResponseModel):
    """One profile answer and the steps it shaped."""

    field: ProfileField
    value: str = Field(description="The answer as stored, e.g. 'umm_al_quwain', 'resident', 'true'")
    step_ids: list[str]


class SkippedService(ResponseModel):
    """A service of this life event that the person's answers rule out."""

    service_id: str
    title: str
    reason: str
    field: ProfileField


class Journey(ResponseModel):
    id: str
    title: str
    life_event_id: str
    context_revision: int
    is_stale: bool
    stages: list[Stage]
    steps: list[JourneyStep]
    dependencies: list[Dependency]
    personalization: list[PersonalizationEffect]
    skipped: list[SkippedService]
    notices: list[str]
    agent_steps: list[AgentStep]
    created_at: UtcDateTime
    updated_at: UtcDateTime


class CreateJourneyRequest(RequestModel):
    discovery_id: IdText
    service_ids: list[IdText] = Field(min_length=1, max_length=20)


class ReplanRequest(RequestModel):
    """Must be an empty JSON object."""


class DocumentProgressUpdate(RequestModel):
    document_id: IdText
    status: DocumentStatus


class StepUpdateRequest(RequestModel):
    progress: Progress | None = None
    document_progress: list[DocumentProgressUpdate] | None = Field(default=None, max_length=50)

    @model_validator(mode="after")
    def _at_least_one(self) -> "StepUpdateRequest":
        if self.progress is None and self.document_progress is None:
            raise ValueError("Provide progress, document_progress, or both.")
        return self
