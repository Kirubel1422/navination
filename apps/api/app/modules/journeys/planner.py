"""Agentic journey planning with a verified-rule guard.

The AI agent writes the plan: stages, steps, instructions, preparation checklists, per-step
assessments and advisory dependencies, tailored to the request and profile. Afterwards the
guard enforces the few officially verified "must happen first" rules from the reviewed catalog:

- a verified required edge whose condition matches the profile becomes a hard dependency, and
  its prerequisite is inserted or moved to an earlier stage if the agent got that wrong;
- a verified edge whose condition is unknown becomes advisory, with a review note;
- every agent-proposed dependency is advisory and can never block a step.
"""

import hashlib
import re
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session as DbSession

from app.agent import prompts
from app.agent.drafts import PlanDraft, StepDraft
from app.agent.runner import execute, trace_json
from app.agent.runtime import AgentContext, FinishTool
from app.agent.tools import catalog_tools, compact_service, web_tools
from app.agent.web import get_official_web
from app.core.config import get_settings
from app.core.i18n import field_name
from app.db.models import AiService, GuestSession
from app.knowledge.repository import Knowledge
from app.modules.services import registry
from app.modules.services.evaluation import evaluate_rule

THEN = {"en": "Then", "ar": "بعد ذلك"}
THEN_DESC = {
    "en": "Steps that must wait for earlier ones under a verified rule.",
    "ar": "خطوات يجب أن تنتظر خطوات سابقة بموجب قاعدة موثقة.",
}


@dataclass
class PlannedStep:
    key: str
    service_id: str
    order_group: int
    title: dict[str, str]
    instructions: dict[str, str]
    checklist: list[dict[str, Any]]
    assessment: dict[str, Any]
    selected: bool


@dataclass
class PlanResult:
    status: str
    title: dict[str, str]
    stages: list[dict[str, Any]]
    steps: list[PlannedStep]
    dependencies: list[dict[str, Any]]
    notices: list[dict[str, Any]] = field(default_factory=list)  # {"key", "params"} or {"text": L}
    agent_steps: list[dict[str, str]] = field(default_factory=list)
    unsupported_reason: dict[str, str] | None = None

    def hard_prerequisites(self, key: str) -> list[str]:
        return [d["from"] for d in self.dependencies if d["kind"] == "required" and d["to"] == key]


def normalize_text(text: str) -> str:
    return re.sub(r"\W+", " ", text.lower()).strip()


def step_signature(service_id: str, hard_prereq_services: list[str]) -> str:
    payload = service_id + "|" + ",".join(sorted(hard_prereq_services))
    return hashlib.sha256(payload.encode()).hexdigest()[:32]


def _service_brief(kb: Knowledge, record: registry.ServiceRecord) -> dict[str, Any]:
    if record.origin == "catalog":
        return {"origin": "catalog", **compact_service(kb, record.id, with_documents=True)}
    return {
        "service_id": record.id,
        "origin": record.origin,
        "title": record.title["en"],
        "summary": record.summary["en"],
        "entity": record.entity["en"],
        "verification_status": record.verification_status,
        "documents": [d["text"]["en"] for d in record.documents],
        "sources": [
            {"source_id": s.id, "url": s.url, "title": s.title["en"]} for s in record.sources
        ],
    }


def _verified_rules(
    kb: Knowledge, service_ids: set[str], profile: dict[str, Any]
) -> list[dict[str, Any]]:
    rules = []
    for dep in kb.dependencies:
        if dep.kind != "required" or not ({dep.from_service_id, dep.to_service_id} & service_ids):
            continue
        outcome = evaluate_rule(dep.condition, profile)
        if outcome == "mismatch":
            continue
        rules.append(
            {
                "prerequisite_service_id": dep.from_service_id,
                "dependent_service_id": dep.to_service_id,
                "applies": "yes"
                if outcome == "match"
                else "only if profile matches " + str(dep.condition),
                "explanation": dep.explanation["en"],
            }
        )
    return rules


def _checker(db: DbSession, kb: Knowledge, session_id: str, selected: list[str], ctx: AgentContext):  # type: ignore[no-untyped-def]
    def check(draft: PlanDraft) -> list[str]:
        problems: list[str] = []
        if draft.status == "unsupported":
            if draft.unsupported_reason is None:
                problems.append("status=unsupported needs unsupported_reason.")
            return problems
        if not draft.stages:
            return ["status=planned needs at least one stage."]
        keys: dict[str, int] = {}
        used: dict[str, str] = {}
        for stage_index, stage in enumerate(draft.stages):
            for step in stage.steps:
                where = f"step {step.key!r}"
                if step.key in keys:
                    problems.append(f"{where}: duplicate step key.")
                keys[step.key] = stage_index
                if (step.service_id is None) == (step.web_service is None):
                    problems.append(f"{where}: give exactly one of service_id or web_service.")
                if step.service_id is not None:
                    known = step.service_id in kb.services or (
                        (row := db.get(AiService, step.service_id)) is not None
                        and row.session_id == session_id
                    )
                    if not known:
                        problems.append(f"{where}: unknown service_id {step.service_id!r}.")
                    elif step.service_id in used:
                        problems.append(
                            f"{where}: service {step.service_id} already used by step {used[step.service_id]!r}."
                        )
                    used[step.service_id] = step.key
                if step.web_service is not None:
                    problems += registry.check_web_draft(step.web_service, ctx, where)
        for stage_index, stage in enumerate(draft.stages):
            for step in stage.steps:
                for dep in step.depends_on:
                    if dep not in keys:
                        problems.append(f"step {step.key!r}: depends_on unknown key {dep!r}.")
                    elif keys[dep] >= stage_index:
                        problems.append(
                            f"step {step.key!r}: depends_on {dep!r} must be in an earlier stage."
                        )
        missing = [sid for sid in selected if sid not in used]
        if missing:
            problems.append(f"Every selected service needs a step; missing: {', '.join(missing)}.")
        return problems

    return check


def _checklist(record: registry.ServiceRecord, key: str, step: StepDraft) -> list[dict[str, Any]]:
    items = []
    for index, item in enumerate(step.checklist):
        source_ids = sorted(
            {sid for ref in item.source_refs if (sid := record.ref_to_source_id(ref))}
        )
        items.append(
            {
                "id": f"{key}.c{index + 1}",
                "text": item.text.model_dump(),
                "source_ids": source_ids,
                "ai_generated": True,
            }
        )
    return items


def _catalog_checklist(record: registry.ServiceRecord, key: str) -> list[dict[str, Any]]:
    return [
        {
            "id": f"{key}.c{i + 1}",
            "text": d["text"],
            "source_ids": d["source_ids"],
            "ai_generated": False,
        }
        for i, d in enumerate(record.documents)
    ]


def generate_plan(
    db: DbSession,
    session: GuestSession,
    kb: Knowledge,
    *,
    request: str,
    interpreted_need: dict[str, str] | None,
    selected: list[str],
    profile: dict[str, Any],
    previous: dict[str, Any] | None = None,
) -> PlanResult:
    records = {sid: registry.resolve(db, kb, session.id, sid) for sid in selected}
    selected_records = [r for r in records.values() if r is not None]
    web = get_official_web(get_settings())
    ctx = AgentContext()
    payload = {
        "REQUEST": request,
        "INTERPRETED_NEED": (interpreted_need or {}).get("en"),
        "PROFILE": profile,
        "LOCALE": session.locale,
        "SELECTED": [_service_brief(kb, r) for r in selected_records],
        "VERIFIED_RULES": _verified_rules(kb, set(selected), profile),
        "PREVIOUS_PLAN": previous,
        "WEB_TOOLS": {"fetch": web.fetch_enabled, "search": web.search_available},
    }
    draft = execute(
        system=prompts.PLAN,
        payload=payload,
        tools=catalog_tools(kb, ctx) + web_tools(web, ctx),
        finish=FinishTool(
            "submit_plan",
            "Submit the staged plan (or status=unsupported).",
            PlanDraft,
            _checker(db, kb, session.id, [r.id for r in selected_records], ctx),
        ),
        ctx=ctx,
        # SELECTED already carries the reviewed details; research only pays off with web search.
        research=web.search_available,
    )
    if draft.status == "unsupported":
        return PlanResult(
            status="unsupported",
            title=draft.title.model_dump(),
            stages=[],
            steps=[],
            dependencies=[],
            agent_steps=trace_json(ctx),
            unsupported_reason=(
                draft.unsupported_reason.model_dump() if draft.unsupported_reason else None
            ),
        )
    return _apply_guard(db, session, kb, draft, selected, profile, ctx)


def _apply_guard(
    db: DbSession,
    session: GuestSession,
    kb: Knowledge,
    draft: PlanDraft,
    selected: list[str],
    profile: dict[str, Any],
    ctx: AgentContext,
) -> PlanResult:
    stages = [
        {"title": s.title.model_dump(), "description": s.description.model_dump()}
        for s in draft.stages
    ]
    steps: list[PlannedStep] = []
    advisory: list[dict[str, Any]] = []
    for stage_index, stage in enumerate(draft.stages):
        for step in stage.steps:
            if step.web_service is not None:
                record = registry.save_web_service(db, session.id, step.web_service, ctx, None)
            else:
                record = registry.resolve(db, kb, session.id, step.service_id or "")
            assert record is not None
            steps.append(
                PlannedStep(
                    key=step.key,
                    service_id=record.id,
                    order_group=stage_index,
                    title=step.title.model_dump(),
                    instructions=step.instructions.model_dump(),
                    checklist=_checklist(record, step.key, step),
                    assessment=registry.stored_assessment(record, step.assessment, profile),
                    selected=record.id in selected,
                )
            )
            for dep in step.depends_on:
                advisory.append(
                    {
                        "from": dep,
                        "to": step.key,
                        "kind": "recommended",
                        "explanation": (step.dependency_note or step.instructions).model_dump(),
                        "source_ids": [],
                    }
                )

    notices: list[dict[str, Any]] = [{"text": n.model_dump()} for n in draft.notices]
    by_service = {s.service_id: s for s in steps}
    hard: list[dict[str, Any]] = []
    inserted: set[str] = set()
    for dep in kb.dependencies:
        if dep.kind != "required" or dep.to_service_id not in by_service:
            continue
        outcome = evaluate_rule(dep.condition, profile)
        dependent = by_service[dep.to_service_id]
        params = {
            "dependent": kb.services[dep.to_service_id].title,
            "prerequisite": kb.services[dep.from_service_id].title,
            "explanation": dep.explanation,
        }
        if outcome == "unknown":
            assert dep.condition is not None
            notices.append(
                {
                    "key": "journey_conditional_edge",
                    "params": {
                        "prereq": params["prerequisite"],
                        "target": params["dependent"],
                        "field": {
                            loc: field_name(loc, dep.condition["field"]) for loc in ("en", "ar")
                        },
                        "explanation": dep.explanation,
                    },
                }
            )
            if dep.from_service_id in by_service:
                advisory.append(
                    {
                        "from": by_service[dep.from_service_id].key,
                        "to": dependent.key,
                        "kind": "recommended",
                        "explanation": dep.explanation,
                        "source_ids": list(dep.source_ids),
                    }
                )
            continue
        if outcome != "match":
            continue
        if dep.from_service_id not in by_service:
            record = registry.from_catalog(kb, kb.services[dep.from_service_id])
            key = f"verified-{dep.from_service_id}"[:48]
            added = PlannedStep(
                key=key,
                service_id=record.id,
                order_group=dependent.order_group,
                title=record.title,
                instructions=record.summary,
                checklist=_catalog_checklist(record, key),
                assessment={
                    "relevance": "potentially_relevant",
                    "reasons": [{"text": dep.explanation, "source_ids": list(dep.source_ids)}],
                    "missing_profile_fields": [],
                },
                selected=False,
            )
            steps.append(added)
            inserted.add(key)
            by_service[record.id] = added
            notices.append({"key": "guard_added_step", "params": params})
        hard.append(
            {
                "from": by_service[dep.from_service_id].key,
                "to": dependent.key,
                "kind": "required",
                "explanation": dep.explanation,
                "source_ids": list(dep.source_ids),
            }
        )

    # Push dependents after their verified prerequisites. The agent's own ordering is kept too
    # (a step it placed after a moved step moves along); if the two conflict, only the verified
    # rules are applied. Hard edges are acyclic by seed validation.
    by_key = {s.key: s for s in steps}
    original = {s.key: s.order_group for s in steps}
    ai_order = [e for e in advisory if e["from"] in by_key and e["kind"] == "recommended"]
    if not _push(by_key, hard + ai_order):
        for step in steps:
            step.order_group = original[step.key]
        _push(by_key, hard)
    for edge in hard:
        moved = original[edge["to"]] != by_key[edge["to"]].order_group
        if moved and edge["from"] not in inserted:
            notices.append(
                {
                    "key": "guard_moved_step",
                    "params": {
                        "dependent": by_key[edge["to"]].title,
                        "prerequisite": by_key[edge["from"]].title,
                        "explanation": edge["explanation"],
                    },
                }
            )
    # An inserted prerequisite sits in the stage its dependent originally had, and the dependent
    # moves later; advisory edges that now point backwards are dropped.
    used = sorted({s.order_group for s in steps})
    remap = {old: new for new, old in enumerate(used)}
    final_stages = [
        stages[old] if old < len(stages) else {"title": THEN, "description": THEN_DESC}
        for old in used
    ]
    for step in steps:
        step.order_group = remap[step.order_group]
    hard_pairs = {(e["from"], e["to"]) for e in hard}
    dependencies = hard + [
        e
        for e in advisory
        if (e["from"], e["to"]) not in hard_pairs
        and e["from"] in by_key
        and by_key[e["from"]].order_group < by_key[e["to"]].order_group
    ]
    steps.sort(key=lambda s: (s.order_group, s.key))
    return PlanResult(
        status="planned",
        title=draft.title.model_dump(),
        stages=final_stages,
        steps=steps,
        dependencies=dependencies,
        notices=notices,
        agent_steps=trace_json(ctx),
    )


def _push(by_key: dict[str, PlannedStep], edges: list[dict[str, Any]]) -> bool:
    """Move dependents to later stages until every edge points forward. False if it cycles."""
    for _ in range(len(by_key) + 1):
        changed = False
        for edge in edges:
            pre, dst = by_key[edge["from"]], by_key[edge["to"]]
            if dst.order_group <= pre.order_group:
                dst.order_group = pre.order_group + 1
                changed = True
        if not changed:
            return True
    return False


def previous_summary(plan: dict[str, Any], steps: list[Any]) -> dict[str, Any]:
    """What the agent sees of the previous plan when replanning (for stable keys and wording)."""
    return {
        "title": plan.get("title", {}).get("en"),
        "steps": [
            {
                "key": s.key,
                "service_id": s.service_id,
                "stage": s.order_group,
                "title": s.title.get("en"),
                "checklist": [c["text"]["en"] for c in s.checklist],
                "user_progress": s.progress,
            }
            for s in steps
        ],
    }
