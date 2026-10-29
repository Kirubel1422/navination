"""Reviewed-rule helpers that act as guardrails around the AI agent.

The agent decides relevance and ordering. These helpers only evaluate the conditions attached to
officially verified dependencies (three-valued: match, mismatch, unknown), which is what keeps the
few verified "must happen first" rules enforced in AI-generated plans.
"""

from typing import Any, Literal

from app.knowledge.repository import Knowledge

Outcome = Literal["match", "mismatch", "unknown"]


def evaluate_rule(rule: dict[str, Any] | None, profile: dict[str, Any]) -> Outcome:
    if rule is None:
        return "match"
    value = profile.get(rule["field"])
    if value is None:
        return "unknown"
    return "match" if value in rule["in"] else "mismatch"


def readiness_of(kb: Knowledge, service_id: str, profile: dict[str, Any]) -> str:
    """Whether a verified required prerequisite applies to this catalog service for this profile."""
    outcomes = [
        evaluate_rule(d.condition, profile)
        for d in kb.dependencies
        if d.to_service_id == service_id and d.kind == "required"
    ]
    if "match" in outcomes:
        return "prerequisites_needed"
    if "unknown" in outcomes:
        return "unknown"
    return "ready"
