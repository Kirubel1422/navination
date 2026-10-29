"""How the optional profile shaped a plan, derived from the reviewed catalog (never from model
wording, so it is reliable and checkable):

- a step is tailored by a profile field when one of its published criteria (profile rule)
  matches the answer, when a verified prerequisite conditioned on that field applies to it, or
  when the catalog has guidance for that answer (profile hint, e.g. the emirate's authority);
- a service of the same life event is "not needed for you" when one of its criteria does not
  match the answer (e.g. the Mabrouk Ma Yak bundle for UAE nationals, when you are a resident).
"""

from typing import Any

from app.knowledge.repository import Knowledge
from app.modules.services.evaluation import evaluate_rule


def _answered(profile: dict[str, Any], field: str) -> bool:
    return profile.get(field) is not None


def _hint_key(value: Any) -> str:
    return str(value).lower() if isinstance(value, bool) else str(value)


def step_tailoring(
    kb: Knowledge, service_id: str, profile: dict[str, Any], locale: str
) -> tuple[list[str], str | None]:
    """Profile fields that shaped this step, and the catalog's guidance for the answer given."""
    service = kb.services.get(service_id)
    if service is None:
        return [], None
    fields: set[str] = set()
    for criterion in service.criteria:
        rule = criterion.rule
        if rule and _answered(profile, rule["field"]) and evaluate_rule(rule, profile) == "match":
            fields.add(rule["field"])
    for dep in kb.dependencies:
        cond = dep.condition
        if (
            cond
            and service_id in (dep.from_service_id, dep.to_service_id)
            and _answered(profile, cond["field"])
            and evaluate_rule(cond, profile) == "match"
        ):
            fields.add(cond["field"])
    note = None
    for hint in service.profile_hints:
        value = profile.get(hint["field"])
        text = hint["values"].get(_hint_key(value)) if value is not None else None
        if text:
            fields.add(hint["field"])
            note = text.get(locale) or text.get("en")
    return sorted(fields), note


def not_needed(
    kb: Knowledge, planned_service_ids: set[str], profile: dict[str, Any], locale: str
) -> list[dict[str, Any]]:
    """Services of the plan's life events that the answers rule out, with the published reason."""
    events = {
        event
        for sid in planned_service_ids
        if sid in kb.services
        for event in kb.services[sid].life_event_ids
    }
    skipped = []
    for service in sorted(kb.services.values(), key=lambda s: s.position):
        if service.id in planned_service_ids or not events.intersection(service.life_event_ids):
            continue
        for criterion in service.criteria:
            rule = criterion.rule
            if (
                rule
                and _answered(profile, rule["field"])
                and evaluate_rule(rule, profile) == "mismatch"
            ):
                skipped.append(
                    {
                        "service_id": service.id,
                        "title": service.title[locale],
                        "reason": criterion.text[locale],
                        "field": rule["field"],
                    }
                )
                break
    return skipped
