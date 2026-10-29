"""Schemas for what the agents submit. They are also the JSON schemas of the `submit_*` tools.

All user-facing text is bilingual ({en, ar}) so a language switch re-renders AI content without
another model call. Source references are either reviewed catalog source IDs or URLs of official
pages the agent actually read during the run.
"""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

Relevance = Literal["potentially_relevant", "more_information_needed", "criterion_mismatch"]
ProfileFieldName = Literal["emirate", "residency_status", "life_stage", "degree_issued_outside_uae"]
Slug = Annotated[str, StringConstraints(pattern=r"^[a-z0-9][a-z0-9_-]{0,47}$")]
Ref = Annotated[str, StringConstraints(min_length=1, max_length=400)]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class L(Strict):
    """Bilingual text."""

    en: str = Field(min_length=1, max_length=1500)
    ar: str = Field(min_length=1, max_length=1500)


class ItemDraft(Strict):
    text: L
    source_refs: list[Ref] = Field(default_factory=list, max_length=6)


class ReasonDraft(Strict):
    text: L
    source_refs: list[Ref] = Field(default_factory=list, max_length=6)


class Assessment(Strict):
    """How a service fits this person. Never an eligibility decision."""

    relevance: Relevance
    reasons: list[ReasonDraft] = Field(min_length=1, max_length=6)
    missing_profile_fields: list[ProfileFieldName] = Field(default_factory=list, max_length=4)


class WebServiceDraft(Strict):
    """A service found on an official website the agent read in this run."""

    title: L
    summary: L
    entity: L
    jurisdiction: L
    authority: L
    official_url: Ref | None = None
    support_url: Ref | None = None
    source_urls: list[Ref] = Field(min_length=1, max_length=5)
    criteria: list[ItemDraft] = Field(default_factory=list, max_length=8)
    documents: list[ItemDraft] = Field(default_factory=list, max_length=10)
    fee_text: L | None = None
    processing_time_text: L | None = None


class ContactDraft(Strict):
    """A real point of contact. The phone must appear on an official page read in this run."""

    label: L = Field(description="Who answers, e.g. ICP call centre / MoHESR customer service")
    phone: str = Field(min_length=3, max_length=30, description="Exactly as written on the page")
    email: str | None = Field(default=None, max_length=120)
    hours: L | None = None
    source_ref: Ref = Field(description="URL of the fetched page where this number appears")


class CenterDraft(Strict):
    """A service centre returned by find_service_centers in this run."""

    place_id: str = Field(min_length=1, max_length=80)
    note: L | None = Field(default=None, description="Why this centre, what it handles, hours")


class ReachDraft(Strict):
    """How to reach a person: phone contacts, nearby centres and a Google Maps search phrase."""

    contacts: list[ContactDraft] = Field(default_factory=list, max_length=4)
    centers: list[CenterDraft] = Field(default_factory=list, max_length=5)
    map_query: str | None = Field(
        default=None,
        max_length=120,
        description="Google Maps search for the right kind of centre, e.g. 'Tasheel centre'",
    )


class ResultDraft(Strict):
    kind: Literal["catalog", "web"]
    service_id: str | None = Field(default=None, description="Catalog service_id when kind=catalog")
    web_service: WebServiceDraft | None = Field(default=None, description="Required when kind=web")
    assessment: Assessment
    reach: ReachDraft | None = Field(
        default=None, description="Phone contacts / nearby centres when the person asks for them"
    )


class OptionDraft(Strict):
    id: Slug
    label: L


class ClarificationDraft(Strict):
    question: L
    options: list[OptionDraft] = Field(min_length=2, max_length=5)


class TopicDraft(Strict):
    id: Slug = Field(
        description="A catalog life_event_id when one fits, otherwise a new short slug"
    )
    label: L


class DiscoveryDraft(Strict):
    status: Literal["ready", "needs_clarification", "no_match"]
    interpreted_need: L
    answer: L | None = Field(
        default=None,
        description="Your direct reply to the person, as a knowledgeable guide (2-4 sentences)",
    )
    answer_refs: list[Ref] = Field(default_factory=list, max_length=6)
    topic: TopicDraft | None = None
    clarification: ClarificationDraft | None = None
    results: list[ResultDraft] = Field(
        default_factory=list, max_length=8, description="Best match first, ordered for this person"
    )
    notices: list[L] = Field(default_factory=list, max_length=4)


class StepDraft(Strict):
    key: Slug
    service_id: str | None = Field(
        default=None, description="Catalog service_id or an already known web service id (web-...)"
    )
    web_service: WebServiceDraft | None = Field(
        default=None, description="A new official service found while planning (no service_id)"
    )
    title: L
    instructions: L
    assessment: Assessment
    checklist: list[ItemDraft] = Field(default_factory=list, max_length=10)
    depends_on: list[Slug] = Field(default_factory=list, max_length=6)
    dependency_note: L | None = None


class StageDraft(Strict):
    title: L
    description: L
    steps: list[StepDraft] = Field(min_length=1, max_length=8)


class PlanDraft(Strict):
    status: Literal["planned", "unsupported"]
    unsupported_reason: L | None = None
    title: L
    stages: list[StageDraft] = Field(default_factory=list, max_length=8)
    notices: list[L] = Field(default_factory=list, max_length=5)


class ActionDraft(Strict):
    type: Literal["view_step", "open_official", "open_support"]
    step_id: str | None = None
    service_id: str | None = None


class CoachDraft(Strict):
    answer: str = Field(min_length=1, max_length=4000)
    grounding_status: Literal["grounded", "insufficient_evidence"]
    citation_refs: list[Ref] = Field(default_factory=list, max_length=8)
    suggested_actions: list[ActionDraft] = Field(default_factory=list, max_length=4)
    reach: ReachDraft | None = None


class NearbyDraft(Strict):
    """Where and how to get a service done in person or by phone, for this person."""

    message: L = Field(description="Your direct reply: which centres suit and anything to know")
    reach: ReachDraft
