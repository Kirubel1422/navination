"""Anonymous navigation outcomes, published back as an open dataset (root cause R5: navigation
failures should drive service improvement).

Nothing personal is stored: no query text, no session or profile, only the day, the outcome, the
topic the agent assigned, the language and (for plans) the seconds from first search to plan.
"""

from collections import defaultdict
from datetime import UTC, datetime, timedelta
from statistics import median
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from app.db.models import NavEvent


def record(
    db: DbSession,
    *,
    kind: str,
    status: str,
    topic: str | None,
    locale: str,
    results: int = 0,
    seconds: int | None = None,
) -> None:
    db.add(
        NavEvent(
            day=datetime.now(UTC).date(),
            kind=kind,
            status=status,
            topic=(topic or None) and topic[:80],
            locale=locale,
            results=results,
            seconds=seconds,
        )
    )


def gaps(db: DbSession, days: int = 90) -> list[dict[str, Any]]:
    """Weekly counts per topic and outcome, plus the median time from first search to a plan."""
    since = datetime.now(UTC).date() - timedelta(days=days)
    buckets: dict[tuple[str, str], dict[str, Any]] = defaultdict(
        lambda: {
            "searches": 0,
            "ready": 0,
            "needs_clarification": 0,
            "no_match": 0,
            "plans": 0,
            "seconds": [],
        }
    )
    for event in db.scalars(select(NavEvent).where(NavEvent.day >= since)):
        week = (event.day - timedelta(days=event.day.weekday())).isoformat()
        bucket = buckets[(week, event.topic or "unassigned")]
        if event.kind == "search":
            bucket["searches"] += 1
            if event.status in ("ready", "needs_clarification", "no_match"):
                bucket[event.status] += 1
        elif event.kind == "plan":
            bucket["plans"] += 1
            if event.seconds is not None:
                bucket["seconds"].append(event.seconds)
    rows = []
    for (week, topic), b in sorted(buckets.items(), reverse=True):
        rows.append(
            {
                "week": week,
                "topic": topic,
                "searches": b["searches"],
                "ready": b["ready"],
                "needs_clarification": b["needs_clarification"],
                "no_match": b["no_match"],
                "plans": b["plans"],
                "median_seconds_to_plan": int(median(b["seconds"])) if b["seconds"] else None,
            }
        )
    return rows
