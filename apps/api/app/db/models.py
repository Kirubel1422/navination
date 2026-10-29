"""Persistence models.

Knowledge tables (kb_*) are replaced by the idempotent seed import. Guest tables reference
service IDs as stable strings so knowledge can be re-imported without touching guest data.
Localized knowledge fields are stored as explicit *_en / *_ar columns.
"""

from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    TypeDecorator,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class UTCDateTime(TypeDecorator[datetime]):
    """Stores naive UTC and always returns timezone-aware UTC datetimes."""

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: Any) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is not None:
            value = value.astimezone(UTC)
        return value.replace(tzinfo=None)

    def process_result_value(self, value: datetime | None, dialect: Any) -> datetime | None:
        return value.replace(tzinfo=UTC) if value is not None else None


class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------- knowledge


class KbSource(Base):
    __tablename__ = "kb_sources"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    title_en: Mapped[str] = mapped_column(Text)
    title_ar: Mapped[str] = mapped_column(Text)
    url: Mapped[str | None] = mapped_column(Text, nullable=True)
    publisher_en: Mapped[str] = mapped_column(Text)
    publisher_ar: Mapped[str] = mapped_column(Text)
    checked_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    source_updated_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    verification_status: Mapped[str] = mapped_column(String(20))
    review_note: Mapped[str | None] = mapped_column(Text, nullable=True)


class KbLifeEvent(Base):
    __tablename__ = "kb_life_events"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    label_en: Mapped[str] = mapped_column(Text)
    label_ar: Mapped[str] = mapped_column(Text)
    keywords: Mapped[dict[str, Any]] = mapped_column(JSON)
    facets: Mapped[list[dict[str, Any]]] = mapped_column(JSON)
    clarification_prompt_en: Mapped[str | None] = mapped_column(Text, nullable=True)
    clarification_prompt_ar: Mapped[str | None] = mapped_column(Text, nullable=True)
    examples: Mapped[dict[str, Any]] = mapped_column(JSON)


class KbService(Base):
    __tablename__ = "kb_services"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    position: Mapped[int] = mapped_column(Integer)
    life_event_ids: Mapped[list[str]] = mapped_column(JSON)
    facets: Mapped[list[str]] = mapped_column(JSON)
    title_en: Mapped[str] = mapped_column(Text)
    title_ar: Mapped[str] = mapped_column(Text)
    summary_en: Mapped[str] = mapped_column(Text)
    summary_ar: Mapped[str] = mapped_column(Text)
    entity_en: Mapped[str] = mapped_column(Text)
    entity_ar: Mapped[str] = mapped_column(Text)
    jurisdiction_en: Mapped[str] = mapped_column(Text)
    jurisdiction_ar: Mapped[str] = mapped_column(Text)
    authority_en: Mapped[str] = mapped_column(Text)
    authority_ar: Mapped[str] = mapped_column(Text)
    fee_text_en: Mapped[str | None] = mapped_column(Text, nullable=True)
    fee_text_ar: Mapped[str | None] = mapped_column(Text, nullable=True)
    processing_time_text_en: Mapped[str | None] = mapped_column(Text, nullable=True)
    processing_time_text_ar: Mapped[str | None] = mapped_column(Text, nullable=True)
    official_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    support_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    verification_status: Mapped[str] = mapped_column(String(20))
    keywords: Mapped[dict[str, Any]] = mapped_column(JSON)
    profile_hints: Mapped[list[dict[str, Any]]] = mapped_column(JSON)
    source_ids: Mapped[list[str]] = mapped_column(JSON)
    review_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    requirements: Mapped[list["KbRequirement"]] = relationship(
        back_populates="service", order_by="KbRequirement.position", cascade="all, delete-orphan"
    )


class KbRequirement(Base):
    __tablename__ = "kb_requirements"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    service_id: Mapped[str] = mapped_column(ForeignKey("kb_services.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String(20))  # criterion | document
    position: Mapped[int] = mapped_column(Integer)
    text_en: Mapped[str] = mapped_column(Text)
    text_ar: Mapped[str] = mapped_column(Text)
    source_ids: Mapped[list[str]] = mapped_column(JSON)
    rule: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    service: Mapped[KbService] = relationship(back_populates="requirements")


class KbDependency(Base):
    __tablename__ = "kb_dependencies"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    from_service_id: Mapped[str] = mapped_column(ForeignKey("kb_services.id", ondelete="CASCADE"))
    to_service_id: Mapped[str] = mapped_column(ForeignKey("kb_services.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String(20))  # required | recommended
    explanation_en: Mapped[str] = mapped_column(Text)
    explanation_ar: Mapped[str] = mapped_column(Text)
    source_ids: Mapped[list[str]] = mapped_column(JSON)
    condition: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)


class KbGlossaryTerm(Base):
    __tablename__ = "kb_glossary"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    terms: Mapped[dict[str, Any]] = mapped_column(JSON)
    definition_en: Mapped[str] = mapped_column(Text)
    definition_ar: Mapped[str] = mapped_column(Text)
    source_ids: Mapped[list[str]] = mapped_column(JSON)


class KbMeta(Base):
    __tablename__ = "kb_meta"

    key: Mapped[str] = mapped_column(String(80), primary_key=True)
    value: Mapped[str] = mapped_column(Text)


# ---------------------------------------------------------------- guest state


class GuestSession(Base):
    __tablename__ = "guest_sessions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    locale: Mapped[str] = mapped_column(String(2))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime, index=True)
    context_revision: Mapped[int] = mapped_column(Integer, default=0)
    emirate: Mapped[str | None] = mapped_column(String(32), nullable=True)
    residency_status: Mapped[str | None] = mapped_column(String(16), nullable=True)
    life_stage: Mapped[str | None] = mapped_column(String(16), nullable=True)
    degree_issued_outside_uae: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    discoveries: Mapped[list["Discovery"]] = relationship(
        cascade="all, delete-orphan", passive_deletes=True
    )
    journeys: Mapped[list["Journey"]] = relationship(
        cascade="all, delete-orphan", passive_deletes=True
    )
    ai_services: Mapped[list["AiService"]] = relationship(
        cascade="all, delete-orphan", passive_deletes=True
    )


class AiService(Base):
    """A service the agent found on an official website, scoped to one guest session."""

    __tablename__ = "ai_services"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    session_id: Mapped[str] = mapped_column(
        ForeignKey("guest_sessions.id", ondelete="CASCADE"), index=True
    )
    data: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime)


class Discovery(Base):
    __tablename__ = "discoveries"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    session_id: Mapped[str] = mapped_column(
        ForeignKey("guest_sessions.id", ondelete="CASCADE"), index=True
    )
    context_revision: Mapped[int] = mapped_column(Integer)
    query: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(24))
    life_event_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    facet_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    clarification: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    service_ids: Mapped[list[str]] = mapped_column(JSON)
    mode: Mapped[str] = mapped_column(String(16))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime)
    # Bilingual agent output: interpreted need, topic label, notices, per-service assessments
    # ({service_id: {relevance, reasons, missing_profile_fields}}) and the agent's activity.
    interpreted_need: Mapped[dict[str, str] | None] = mapped_column(JSON, nullable=True)
    topic_label: Mapped[dict[str, str] | None] = mapped_column(JSON, nullable=True)
    notices: Mapped[list[dict[str, str]]] = mapped_column(JSON, default=list)
    assessments: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    agent_steps: Mapped[list[dict[str, str]]] = mapped_column(JSON, default=list)
    # The guide's direct reply: {"text": {en, ar}, "sources": [{id, url, title, publisher, ...}]}.
    answer: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)


class Journey(Base):
    __tablename__ = "journeys"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    session_id: Mapped[str] = mapped_column(
        ForeignKey("guest_sessions.id", ondelete="CASCADE"), index=True
    )
    discovery_id: Mapped[str] = mapped_column(String(64))
    query: Mapped[str] = mapped_column(Text)
    life_event_id: Mapped[str] = mapped_column(String(80))
    facet_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    selected_service_ids: Mapped[list[str]] = mapped_column(JSON)
    # Profile used to build the current plan, so a stale plan stays readable as it was.
    profile_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON)
    context_revision: Mapped[int] = mapped_column(Integer)
    change_notices: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime)
    # The agent-generated plan: title, stages, notices, advisory dependencies, guard notices
    # and the agent's activity. Steps hold their own generated content.
    plan: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)

    steps: Mapped[list["JourneyStep"]] = relationship(
        cascade="all, delete-orphan", passive_deletes=True, order_by="JourneyStep.position"
    )
    messages: Mapped[list["CoachMessage"]] = relationship(
        cascade="all, delete-orphan", passive_deletes=True, order_by="CoachMessage.sequence"
    )
    handoffs: Mapped[list["Handoff"]] = relationship(
        cascade="all, delete-orphan", passive_deletes=True
    )


class JourneyStep(Base):
    __tablename__ = "journey_steps"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    journey_id: Mapped[str] = mapped_column(
        ForeignKey("journeys.id", ondelete="CASCADE"), index=True
    )
    service_id: Mapped[str] = mapped_column(String(80))
    position: Mapped[int] = mapped_column(Integer)
    added_as_prerequisite: Mapped[bool] = mapped_column(Boolean, default=False)
    progress: Mapped[str] = mapped_column(String(16), default="not_started")
    document_progress: Mapped[dict[str, str]] = mapped_column(JSON, default=dict)
    # Fingerprint of service and hard prerequisites used to decide progress preservation.
    signature: Mapped[str] = mapped_column(String(64))
    key: Mapped[str] = mapped_column(String(64), default="")
    order_group: Mapped[int] = mapped_column(Integer, default=0)
    title: Mapped[dict[str, str]] = mapped_column(JSON, default=dict)
    instructions: Mapped[dict[str, str]] = mapped_column(JSON, default=dict)
    # [{id, text: {en, ar}, source_ids, ai_generated}]
    checklist: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    assessment: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class CoachMessage(Base):
    __tablename__ = "coach_messages"
    __table_args__ = (UniqueConstraint("journey_id", "client_message_id"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    journey_id: Mapped[str] = mapped_column(
        ForeignKey("journeys.id", ondelete="CASCADE"), index=True
    )
    sequence: Mapped[int] = mapped_column(Integer)
    role: Mapped[str] = mapped_column(String(16))
    content: Mapped[str] = mapped_column(Text)
    step_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    citation_source_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    # Citations to pages the agent read on the web (catalog citations use citation_source_ids).
    web_citations: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    # Phone contacts / nearby centres on assistant messages (see app.agent.reach.store_reach).
    reach: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime)
    # Set on user messages only: idempotency key, payload fingerprint and the stored turn.
    client_message_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    payload_fingerprint: Mapped[str | None] = mapped_column(String(64), nullable=True)
    turn: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)


class Handoff(Base):
    __tablename__ = "handoffs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    journey_id: Mapped[str] = mapped_column(
        ForeignKey("journeys.id", ondelete="CASCADE"), index=True
    )
    step_id: Mapped[str] = mapped_column(String(64))
    service_id: Mapped[str] = mapped_column(String(80))
    kind: Mapped[str] = mapped_column(String(16))
    url: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime)


class OdDataset(Base):
    """One dataset in a government open-data catalogue (Bayanat, Ajman Data), mirrored locally."""

    __tablename__ = "od_datasets"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)  # portal + hash(entity, title)
    portal: Mapped[str] = mapped_column(String(24), index=True)
    title: Mapped[str] = mapped_column(Text)
    entity: Mapped[str] = mapped_column(String(200))
    theme: Mapped[str | None] = mapped_column(String(40), nullable=True)
    last_updated: Mapped[date | None] = mapped_column(Date, nullable=True)
    url: Mapped[str] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    search_text: Mapped[str] = mapped_column(Text)
    synced_at: Mapped[datetime] = mapped_column(UTCDateTime)


class OdSnapshot(Base):
    """The rows of a curated dataset that powers service insights, with provenance."""

    __tablename__ = "od_snapshots"

    key: Mapped[str] = mapped_column(String(80), primary_key=True)
    title: Mapped[str] = mapped_column(Text)
    publisher: Mapped[str] = mapped_column(String(200))
    portal: Mapped[str] = mapped_column(String(24))
    url: Mapped[str] = mapped_column(Text)
    resource_name: Mapped[str] = mapped_column(Text)
    source_updated: Mapped[date | None] = mapped_column(Date, nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(UTCDateTime)
    checksum: Mapped[str] = mapped_column(String(64))
    columns: Mapped[list[str]] = mapped_column(JSON)
    rows: Mapped[list[list[Any]]] = mapped_column(JSON)
    origin: Mapped[str] = mapped_column(String(16))  # "live" (synced) or "bundled" (shipped copy)


class OdSyncRun(Base):
    __tablename__ = "od_sync_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    started_at: Mapped[datetime] = mapped_column(UTCDateTime)
    finished_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(16))
    datasets_indexed: Mapped[int] = mapped_column(Integer, default=0)
    snapshots_ok: Mapped[int] = mapped_column(Integer, default=0)
    snapshots_failed: Mapped[int] = mapped_column(Integer, default=0)
    notes: Mapped[list[str]] = mapped_column(JSON, default=list)


class NavEvent(Base):
    """An anonymous navigation outcome (no query text, no session): the data NaviNation gives
    back to service owners about unmet needs and time to a plan."""

    __tablename__ = "nav_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    day: Mapped[date] = mapped_column(Date, index=True)
    kind: Mapped[str] = mapped_column(String(24))  # search | plan
    status: Mapped[str] = mapped_column(
        String(24)
    )  # ready | needs_clarification | no_match | planned
    topic: Mapped[str | None] = mapped_column(String(80), nullable=True)
    locale: Mapped[str] = mapped_column(String(4))
    results: Mapped[int] = mapped_column(Integer, default=0)
    seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)  # first search -> plan
