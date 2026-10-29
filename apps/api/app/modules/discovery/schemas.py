from typing import Annotated, Literal

from pydantic import Field, StringConstraints

from app.core.schemas import RequestModel, ResponseModel
from app.modules.services.schemas import Location, ServiceCard, Source

QueryText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]
IdText = Annotated[str, StringConstraints(min_length=1, max_length=80)]


class AgentStep(ResponseModel):
    """One tool the AI agent used, for transparency (e.g. a catalog lookup or an official page)."""

    tool: str
    detail: str


class ClarificationOption(ResponseModel):
    id: str
    label: str


class Clarification(ResponseModel):
    id: str
    prompt: str
    options: list[ClarificationOption]


class ClarificationAnswer(RequestModel):
    discovery_id: IdText
    question_id: IdText
    option_id: IdText


class DiscoverRequest(RequestModel):
    query: QueryText
    clarification_answer: ClarificationAnswer | None
    location: Location | None = Field(
        default=None, description="Shared by the person for nearby centres; used, never stored"
    )


class Discovery(ResponseModel):
    id: str
    context_revision: int
    query: str
    interpreted_need: str
    answer: str | None = Field(description="The guide's direct reply to the request")
    answer_sources: list[Source]
    life_event_id: str | None
    status: Literal["ready", "needs_clarification", "no_match"]
    clarification: Clarification | None
    results: list[ServiceCard]
    mode: Literal["ai"]
    notices: list[str]
    agent_steps: list[AgentStep]
