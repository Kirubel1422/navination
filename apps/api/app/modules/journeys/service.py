"""Journey persistence, progress rules, stale-state handling and agentic replanning."""

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session as DbSession

from app.core.errors import AppError, context_stale, not_found, validation_error
from app.core.i18n import LIST_SEPARATOR, render_notices, t
from app.core.timeutil import utcnow
from app.db.models import Discovery, GuestSession
from app.db.models import Journey as JourneyRow
from app.db.models import JourneyStep as StepRow
from app.knowledge.repository import Knowledge
from app.modules.discovery.schemas import AgentStep
from app.modules.journeys import schemas
from app.modules.journeys.personalization import not_needed, step_tailoring
from app.modules.journeys.planner import (
    PlanResult,
    generate_plan,
    normalize_text,
    previous_summary,
    step_signature,
)
from app.modules.services import registry
from app.modules.sessions.service import new_id, profile_of
from app.opendata import navigation


def get_owned_journey(db: DbSession, session: GuestSession, journey_id: str) -> JourneyRow:
    journey = db.get(JourneyRow, journey_id)
    if journey is None or journey.session_id != session.id:
        raise not_found("This plan was not found.")
    return journey


def is_stale(journey: JourneyRow, session: GuestSession) -> bool:
    return journey.context_revision != session.context_revision


def require_fresh(journey: JourneyRow, session: GuestSession) -> None:
    if is_stale(journey, session):
        raise context_stale(
            "Your profile changed after this plan was made. Update the plan before continuing."
        )


def _unsupported(result: PlanResult, locale: str) -> AppError:
    reason = (result.unsupported_reason or {}).get(locale) or (result.unsupported_reason or {}).get(
        "en"
    )
    return context_stale(
        "The AI planner found that this selection no longer fits your situation. "
        "Search again to find services that match.",
        [{"field": "service_ids", "message": reason or "Selection unsupported."}],
    )


def _plan_json(result: PlanResult) -> dict[str, Any]:
    return {
        "title": result.title,
        "stages": result.stages,
        "dependencies": result.dependencies,
        "notices": result.notices,
        "agent_steps": result.agent_steps,
    }


def _signature(result: PlanResult, key: str, service_id: str) -> str:
    by_key = {s.key: s for s in result.steps}
    return step_signature(
        service_id, [by_key[k].service_id for k in result.hard_prerequisites(key)]
    )


def _new_row(result: PlanResult, planned: Any, position: int) -> StepRow:
    return StepRow(
        id=new_id("stp"),
        service_id=planned.service_id,
        position=position,
        added_as_prerequisite=not planned.selected,
        progress="not_started",
        document_progress={item["id"]: "unknown" for item in planned.checklist},
        signature=_signature(result, planned.key, planned.service_id),
        key=planned.key,
        order_group=planned.order_group,
        title=planned.title,
        instructions=planned.instructions,
        checklist=planned.checklist,
        assessment=planned.assessment,
    )


def _carry_reach(result: PlanResult, assessments: dict[str, Any]) -> None:
    """Keep the phone contacts / nearby centres found while searching on the matching steps."""
    for planned in result.steps:
        reach = (assessments.get(planned.service_id) or {}).get("reach")
        if reach and "reach" not in planned.assessment:
            planned.assessment = {**planned.assessment, "reach": reach}


def create_journey(
    db: DbSession, session: GuestSession, kb: Knowledge, body: schemas.CreateJourneyRequest
) -> JourneyRow:
    discovery = db.get(Discovery, body.discovery_id)
    if discovery is None or discovery.session_id != session.id:
        raise not_found("This discovery was not found.")
    if discovery.context_revision != session.context_revision:
        raise context_stale("Your profile changed after this search. Please search again.")
    if discovery.status != "ready":
        raise validation_error(
            "Plans can only be created from ready search results.", "discovery_id"
        )
    if len(set(body.service_ids)) != len(body.service_ids):
        raise validation_error("Each service can only be selected once.", "service_ids")
    if any(sid not in discovery.service_ids for sid in body.service_ids):
        raise validation_error(
            "Selected services must come from this search's results.", "service_ids"
        )

    profile = profile_of(session)
    result = generate_plan(
        db,
        session,
        kb,
        request=discovery.query,
        interpreted_need=discovery.interpreted_need,
        selected=list(body.service_ids),
        profile=profile,
    )
    if result.status != "planned":
        db.rollback()
        raise _unsupported(result, session.locale)
    _carry_reach(result, discovery.assessments or {})
    now = utcnow()
    journey = JourneyRow(
        id=new_id("jrn"),
        session_id=session.id,
        discovery_id=discovery.id,
        query=discovery.query,
        life_event_id=discovery.life_event_id or "ai-plan",
        facet_id=None,
        selected_service_ids=list(body.service_ids),
        profile_snapshot=profile,
        context_revision=session.context_revision,
        change_notices=[],
        created_at=now,
        updated_at=now,
        plan=_plan_json(result) | {"interpreted_need": discovery.interpreted_need},
    )
    db.add(journey)
    for position, planned in enumerate(result.steps):
        journey.steps.append(_new_row(result, planned, position))
    first_search = db.scalar(
        select(func.min(Discovery.created_at)).where(Discovery.session_id == session.id)
    )
    navigation.record(
        db,
        kind="plan",
        status="planned",
        topic=discovery.life_event_id,
        locale=session.locale,
        results=len(result.steps),
        seconds=_seconds_since(first_search, now),
    )
    db.commit()
    return journey


def _seconds_since(start: Any, end: Any) -> int | None:
    """Time from the session's first search to this plan (the challenge's discovery-time KPI)."""
    if start is None:
        return None
    if start.tzinfo is None and end.tzinfo is not None:
        start = start.replace(tzinfo=end.tzinfo)
    return max(0, int((end - start).total_seconds()))


def render_journey(
    kb: Knowledge, journey: JourneyRow, session: GuestSession, db: DbSession
) -> schemas.Journey:
    locale = session.locale
    plan = journey.plan or {}
    step_by_key = {s.key: s for s in journey.steps}
    title_of = {s.key: s.title.get(locale) or s.title.get("en", "") for s in journey.steps}

    dependencies: list[schemas.Dependency] = []
    for dep in plan.get("dependencies", []):
        src, dst = step_by_key.get(dep["from"]), step_by_key.get(dep["to"])
        if src is None or dst is None:
            continue
        dependencies.append(
            schemas.Dependency(
                from_step_id=src.id,
                to_step_id=dst.id,
                kind=dep["kind"],
                explanation=dep["explanation"][locale],
                source_ids=list(dep["source_ids"]),
            )
        )

    profile = journey.profile_snapshot or {}
    steps: list[schemas.JourneyStep] = []
    for row in journey.steps:
        record = registry.resolve(db, kb, session.id, row.service_id)
        if record is None:
            continue
        card = registry.card(kb, record, row.assessment, locale, journey.profile_snapshot)
        notes: list[str] = []
        prereq_ids: list[str] = []
        blockers: list[str] = []
        for dep in plan.get("dependencies", []):
            if dep["to"] != row.key or dep["from"] not in step_by_key:
                continue
            src = step_by_key[dep["from"]]
            prereq_ids.append(src.id)
            key = (
                "step_note_required_before"
                if dep["kind"] == "required"
                else "step_note_recommended_before"
            )
            notes.append(
                t(locale, key, prereq=title_of[src.key], explanation=dep["explanation"][locale])
            )
            if dep["kind"] == "required" and src.progress != "completed":
                blockers.append(src.id)
        if blockers:
            availability = "blocked"
            names = LIST_SEPARATOR[locale].join(
                title_of[s.key] for s in journey.steps if s.id in blockers
            )
            notes.insert(0, t(locale, "step_note_blocked", titles=names))
        elif record.verification_status != "verified" or card.relevance == "criterion_mismatch":
            availability = "review_needed"
        else:
            availability = "ready"
        if record.verification_status != "verified":
            notes.append(t(locale, "step_note_review_needed"))
        if card.relevance == "criterion_mismatch":
            notes.append(t(locale, "step_note_mismatch"))
        tailored_by, tailored_note = step_tailoring(kb, row.service_id, profile, locale)
        steps.append(
            schemas.JourneyStep(
                id=row.id,
                title=row.title.get(locale) or record.title[locale],
                instructions=row.instructions.get(locale) or record.summary[locale],
                checklist=[
                    schemas.ChecklistItem(
                        id=item["id"],
                        text=item["text"][locale],
                        source_ids=[sid for sid in item["source_ids"] if sid in record.source_ids],
                        ai_generated=item["ai_generated"],
                    )
                    for item in row.checklist
                ],
                service_card=card,
                order_group=row.order_group,
                prerequisite_step_ids=prereq_ids,
                document_progress=[
                    schemas.DocumentProgress(
                        document_id=item["id"],
                        status=row.document_progress.get(item["id"], "unknown"),
                    )
                    for item in row.checklist
                ],
                progress=row.progress,  # type: ignore[arg-type]
                availability=availability,  # type: ignore[arg-type]
                blocker_step_ids=blockers,
                notes=notes,
                tailored_by=tailored_by,  # type: ignore[arg-type]
                tailored_note=tailored_note,
            )
        )

    stale = is_stale(journey, session)
    notices = [t(locale, "journey_progress_user_reported")]
    if stale:
        notices.insert(0, t(locale, "journey_stale"))
    for notice in plan.get("notices", []):
        notices += (
            [notice["text"][locale]] if "text" in notice else render_notices(locale, [notice])
        )
    notices += render_notices(locale, journey.change_notices or [])
    stages = plan.get("stages", [])
    return schemas.Journey(
        id=journey.id,
        title=(plan.get("title") or {}).get(locale)
        or t(locale, "journey_title", label=journey.query),
        life_event_id=journey.life_event_id,
        context_revision=journey.context_revision,
        is_stale=stale,
        stages=[
            schemas.Stage(
                order_group=i, title=s["title"][locale], description=s["description"][locale]
            )
            for i, s in enumerate(stages)
        ],
        steps=steps,
        dependencies=dependencies,
        personalization=[
            schemas.PersonalizationEffect(
                field=field,  # type: ignore[arg-type]
                value=str(value).lower() if isinstance(value, bool) else str(value),
                step_ids=[st.id for st in steps if field in st.tailored_by],
            )
            for field, value in profile.items()
            if value is not None
        ],
        skipped=[
            schemas.SkippedService(**item)
            for item in not_needed(kb, {row.service_id for row in journey.steps}, profile, locale)
        ],
        notices=notices,
        agent_steps=[AgentStep(**s) for s in plan.get("agent_steps", [])],
        created_at=journey.created_at,
        updated_at=journey.updated_at,
    )


def _hard_prerequisite_keys(journey: JourneyRow, key: str) -> list[str]:
    return [
        d["from"]
        for d in (journey.plan or {}).get("dependencies", [])
        if d["kind"] == "required" and d["to"] == key
    ]


def update_step(
    db: DbSession,
    session: GuestSession,
    journey: JourneyRow,
    step_id: str,
    body: schemas.StepUpdateRequest,
) -> None:
    require_fresh(journey, session)
    step = next((s for s in journey.steps if s.id == step_id), None)
    if step is None:
        raise not_found("This step was not found in the plan.")
    by_key = {s.key: s for s in journey.steps}
    change: list[dict[str, Any]] = []

    if body.document_progress is not None:
        ids = [d.document_id for d in body.document_progress]
        if len(ids) != len(set(ids)):
            raise validation_error("Each checklist item can only appear once.", "document_progress")
        known = {item["id"] for item in step.checklist}
        unknown = [i for i in ids if i not in known]
        if unknown:
            raise validation_error(
                f"Unknown checklist item for this step: {unknown[0]}", "document_progress"
            )
        updated = dict(step.document_progress)
        for item in body.document_progress:
            updated[item.document_id] = item.status
        step.document_progress = updated

    if body.progress is not None and body.progress != step.progress:
        if body.progress == "completed":
            incomplete = [
                by_key[k].id
                for k in _hard_prerequisite_keys(journey, step.key)
                if k in by_key and by_key[k].progress != "completed"
            ]
            if incomplete:
                db.rollback()
                raise AppError(
                    409,
                    "PREREQUISITES_INCOMPLETE",
                    "Complete the required earlier steps before marking this one completed.",
                    [
                        {"field": "progress", "message": f"Blocked by step {sid}"}
                        for sid in incomplete
                    ],
                )
        was_completed = step.progress == "completed"
        step.progress = body.progress
        if was_completed:
            change += _rollback_downstream(journey, by_key, step.key)

    journey.change_notices = change
    journey.updated_at = utcnow()
    db.commit()


def _rollback_downstream(
    journey: JourneyRow, by_key: dict[str, StepRow], key: str
) -> list[dict[str, Any]]:
    notices: list[dict[str, Any]] = []
    deps = [d for d in (journey.plan or {}).get("dependencies", []) if d["kind"] == "required"]
    queue = [key]
    while queue:
        current = queue.pop(0)
        for dep in deps:
            if dep["from"] != current or dep["to"] not in by_key:
                continue
            row = by_key[dep["to"]]
            if row.progress == "completed":
                row.progress = "not_started"
                notices.append(
                    {
                        "key": "journey_rollback",
                        "params": {"title": row.title, "prereq": by_key[current].title},
                    }
                )
            queue.append(dep["to"])
    return notices


def replan(db: DbSession, session: GuestSession, kb: Knowledge, journey: JourneyRow) -> None:
    profile = profile_of(session)
    result = generate_plan(
        db,
        session,
        kb,
        request=journey.query,
        interpreted_need=(journey.plan or {}).get("interpreted_need"),
        selected=list(journey.selected_service_ids),
        profile=profile,
        previous=previous_summary(journey.plan or {}, journey.steps),
    )
    if result.status != "planned":
        db.rollback()
        raise _unsupported(result, session.locale)

    old_by_service = {s.service_id: s for s in journey.steps}
    notices: list[dict[str, Any]] = [{"key": "journey_replanned", "params": {}}]
    new_rows: list[StepRow] = []
    for position, planned in enumerate(result.steps):
        old = old_by_service.pop(planned.service_id, None)
        if old is None:
            new_rows.append(_new_row(result, planned, position))
            notices.append({"key": "journey_added_step", "params": {"title": planned.title}})
            continue
        signature = _signature(result, planned.key, planned.service_id)
        touched = old.progress != "not_started" or any(
            v != "unknown" for v in old.document_progress.values()
        )
        old_status_by_text = {
            normalize_text(item["text"]["en"]): old.document_progress.get(item["id"], "unknown")
            for item in old.checklist
        }
        if old.signature != signature:
            old.progress = "not_started"
            old.document_progress = {item["id"]: "unknown" for item in planned.checklist}
            if touched:
                notices.append({"key": "journey_reset_step", "params": {"title": planned.title}})
        else:
            # Keep checklist answers whose wording is unchanged.
            old.document_progress = {
                item["id"]: old_status_by_text.get(normalize_text(item["text"]["en"]), "unknown")
                for item in planned.checklist
            }
            if touched:
                notices.append({"key": "journey_kept_step", "params": {"title": planned.title}})
        old.signature = signature
        old.position = position
        old.key = planned.key
        old.order_group = planned.order_group
        old.title = planned.title
        old.instructions = planned.instructions
        old.checklist = planned.checklist
        old.assessment = (
            planned.assessment
            if "reach" in planned.assessment or "reach" not in (old.assessment or {})
            else {**planned.assessment, "reach": old.assessment["reach"]}
        )
        old.added_as_prerequisite = not planned.selected
        new_rows.append(old)
    for removed in old_by_service.values():
        notices.append({"key": "journey_removed_step", "params": {"title": removed.title}})
    journey.steps[:] = new_rows

    by_key = {s.key: s for s in new_rows}
    for row in new_rows:
        if row.progress == "completed" and any(
            by_key[k].progress != "completed"
            for k in result.hard_prerequisites(row.key)
            if k in by_key
        ):
            row.progress = "not_started"
            notices.append({"key": "journey_reset_step", "params": {"title": row.title}})

    journey.plan = _plan_json(result) | {
        "interpreted_need": (journey.plan or {}).get("interpreted_need")
    }
    journey.profile_snapshot = profile
    journey.context_revision = session.context_revision
    journey.change_notices = notices
    journey.updated_at = utcnow()
    db.commit()
