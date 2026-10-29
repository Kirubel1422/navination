"""Load and validate the reviewed seed knowledge (YAML) before import."""

from datetime import date, datetime
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlparse

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError

SEED_DIR = Path(__file__).parent / "seed"
PROFILE_FIELDS = {
    "emirate": {
        "abu_dhabi",
        "dubai",
        "sharjah",
        "ajman",
        "umm_al_quwain",
        "ras_al_khaimah",
        "fujairah",
    },
    "residency_status": {"citizen", "resident", "visitor"},
    "life_stage": {"student", "worker", "parent", "other"},
    "degree_issued_outside_uae": {True, False},
}
# Destinations must be HTTPS on these official or explicitly reviewed hosts.
ALLOWED_HOST_SUFFIXES = (".gov.ae", "u.ae", "uaepass.ae", "gulfnews.com")
DESTINATION_HOST_SUFFIXES = (".gov.ae", "u.ae", "uaepass.ae")


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Localized(Strict):
    en: str = Field(min_length=1)
    ar: str = Field(min_length=1)


class Rule(Strict):
    field: Literal["emirate", "residency_status", "life_stage", "degree_issued_outside_uae"]
    in_: list[Any] = Field(alias="in", min_length=1)


class SeedSource(Strict):
    id: str
    title: Localized
    url: str | None
    publisher: Localized
    checked_at: datetime | None
    source_updated_at: date | None
    verification_status: Literal["verified", "needs_review", "demo"]
    review_note: str | None = None


class SeedFacet(Strict):
    id: str
    label: Localized
    keywords: dict[Literal["en", "ar"], list[str]]


class SeedClarification(Strict):
    prompt: Localized


class SeedLifeEvent(Strict):
    id: str
    label: Localized
    keywords: dict[Literal["en", "ar"], dict[str, float]]
    facets: list[SeedFacet]
    clarification: SeedClarification | None
    examples: dict[Literal["en", "ar"], list[str]]


class SeedRequirement(Strict):
    id: str
    kind: Literal["criterion", "document"]
    text: Localized
    source_ids: list[str]
    rule: Rule | None = None


class SeedHint(Strict):
    field: Literal["emirate", "residency_status", "life_stage", "degree_issued_outside_uae"]
    values: dict[str, Localized]
    source_ids: list[str]


class SeedService(Strict):
    id: str
    life_event_ids: list[str] = Field(min_length=1)
    facets: list[str]
    title: Localized
    summary: Localized
    entity: Localized
    jurisdiction: Localized
    authority: Localized
    fee_text: Localized | None
    processing_time_text: Localized | None
    official_url: str | None
    support_url: str | None
    verification_status: Literal["verified", "needs_review", "demo"]
    review_note: str | None = None
    source_ids: list[str] = Field(min_length=1)
    keywords: dict[Literal["en", "ar"], list[str]]
    requirements: list[SeedRequirement]
    profile_hints: list[SeedHint]


class SeedDependency(Strict):
    id: str
    from_: str = Field(alias="from")
    to: str
    kind: Literal["required", "recommended"]
    explanation: Localized
    source_ids: list[str]
    condition: Rule | None = None


class SeedGlossary(Strict):
    id: str
    terms: dict[Literal["en", "ar"], list[str]]
    definition: Localized
    source_ids: list[str] = Field(min_length=1)


class SeedBundle(Strict):
    sources: list[SeedSource]
    life_events: list[SeedLifeEvent]
    services: list[SeedService]
    dependencies: list[SeedDependency]
    glossary: list[SeedGlossary]


class SeedValidationError(Exception):
    def __init__(self, problems: list[str]) -> None:
        super().__init__("\n".join(problems))
        self.problems = problems


def _read(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle) or []


def load_seed(seed_dir: Path = SEED_DIR) -> SeedBundle:
    raw = {
        name: _read(seed_dir / f"{name}.yaml")
        for name in ("sources", "life_events", "services", "dependencies", "glossary")
    }
    try:
        bundle = SeedBundle.model_validate(raw)
    except ValidationError as exc:
        raise SeedValidationError([str(err) for err in exc.errors()]) from exc
    problems = validate_bundle(bundle)
    if problems:
        raise SeedValidationError(problems)
    return bundle


def _check_url(url: str | None, where: str, problems: list[str], destination: bool) -> None:
    if url is None:
        return
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    suffixes = DESTINATION_HOST_SUFFIXES if destination else ALLOWED_HOST_SUFFIXES
    if parsed.scheme != "https" or not host:
        problems.append(f"{where}: URL must be absolute HTTPS ({url})")
    elif not any(host == s.lstrip(".") or host.endswith(s) for s in suffixes):
        problems.append(
            f"{where}: host {host} is not an allowed {'destination' if destination else 'source'} host"
        )
    if parsed.username or parsed.password:
        problems.append(f"{where}: URL must not contain credentials")


def _duplicates(ids: list[str], label: str, problems: list[str]) -> None:
    seen: set[str] = set()
    for item in ids:
        if item in seen:
            problems.append(f"duplicate {label} id: {item}")
        seen.add(item)


def _check_rule(rule: Rule | None, where: str, problems: list[str]) -> None:
    if rule is None:
        return
    allowed = PROFILE_FIELDS[rule.field]
    for value in rule.in_:
        if value not in allowed:
            problems.append(f"{where}: value {value!r} is not valid for {rule.field}")


def validate_bundle(bundle: SeedBundle) -> list[str]:
    problems: list[str] = []
    sources = {s.id: s for s in bundle.sources}
    services = {s.id: s for s in bundle.services}
    life_events = {e.id: e for e in bundle.life_events}

    _duplicates([s.id for s in bundle.sources], "source", problems)
    _duplicates([e.id for e in bundle.life_events], "life event", problems)
    _duplicates([s.id for s in bundle.services], "service", problems)
    _duplicates([d.id for d in bundle.dependencies], "dependency", problems)
    _duplicates([g.id for g in bundle.glossary], "glossary", problems)
    _duplicates([r.id for s in bundle.services for r in s.requirements], "requirement", problems)

    for source in bundle.sources:
        _check_url(source.url, f"source {source.id}", problems, destination=False)
        if source.verification_status == "verified" and (not source.url or not source.checked_at):
            problems.append(f"source {source.id}: verified sources need a URL and checked_at")

    for event in bundle.life_events:
        facet_ids = [f.id for f in event.facets]
        _duplicates(facet_ids, f"facet in {event.id}", problems)
        if len(facet_ids) > 1 and event.clarification is None:
            problems.append(f"life event {event.id}: multiple facets need a clarification prompt")
        for locale in ("en", "ar"):
            if not event.examples.get(locale):
                problems.append(f"life event {event.id}: missing {locale} examples")
            if not event.keywords.get(locale):
                problems.append(f"life event {event.id}: missing {locale} keywords")

    for service in bundle.services:
        where = f"service {service.id}"
        for event_id in service.life_event_ids:
            if event_id not in life_events:
                problems.append(f"{where}: unknown life event {event_id}")
            else:
                valid_facets = {f.id for f in life_events[event_id].facets}
                for facet in service.facets:
                    if facet not in valid_facets:
                        problems.append(f"{where}: unknown facet {facet} for {event_id}")
        for source_id in service.source_ids:
            if source_id not in sources:
                problems.append(f"{where}: unknown source {source_id}")
        _check_url(service.official_url, f"{where} official_url", problems, destination=True)
        _check_url(service.support_url, f"{where} support_url", problems, destination=True)
        if service.verification_status == "verified" and not any(
            sources[s].verification_status == "verified" for s in service.source_ids if s in sources
        ):
            problems.append(f"{where}: verified services need at least one verified source")
        for locale in ("en", "ar"):
            if not service.keywords.get(locale):
                problems.append(f"{where}: missing {locale} keywords")
        for requirement in service.requirements:
            rwhere = f"requirement {requirement.id}"
            if not requirement.id.startswith(service.id + "."):
                problems.append(f"{rwhere}: id must be prefixed with its service id")
            if not requirement.source_ids:
                problems.append(f"{rwhere}: missing evidence (no source_ids)")
            for source_id in requirement.source_ids:
                if source_id not in service.source_ids:
                    problems.append(f"{rwhere}: source {source_id} is not listed on {service.id}")
            _check_rule(requirement.rule, rwhere, problems)
        for hint in service.profile_hints:
            for value in hint.values:
                if value not in {str(v).lower() for v in PROFILE_FIELDS[hint.field]}:
                    problems.append(f"{where}: hint value {value} invalid for {hint.field}")
            for source_id in hint.source_ids:
                if source_id not in service.source_ids:
                    problems.append(f"{where}: hint source {source_id} not listed on service")

    required_edges: dict[str, set[str]] = {}
    for dep in bundle.dependencies:
        where = f"dependency {dep.id}"
        for endpoint in (dep.from_, dep.to):
            if endpoint not in services:
                problems.append(f"{where}: unknown service {endpoint}")
        if dep.from_ == dep.to:
            problems.append(f"{where}: a service cannot depend on itself")
        if not dep.source_ids:
            problems.append(f"{where}: missing evidence (no source_ids)")
        for source_id in dep.source_ids:
            if source_id not in sources:
                problems.append(f"{where}: unknown source {source_id}")
        _check_rule(dep.condition, where, problems)
        if dep.kind == "required":
            if not any(
                sources[s].verification_status == "verified" for s in dep.source_ids if s in sources
            ):
                problems.append(f"{where}: unsupported mandatory edge (no verified source)")
            required_edges.setdefault(dep.from_, set()).add(dep.to)

    cycle = _find_cycle(required_edges)
    if cycle:
        problems.append("required-dependency cycle: " + " -> ".join(cycle))

    for term in bundle.glossary:
        for source_id in term.source_ids:
            if source_id not in sources:
                problems.append(f"glossary {term.id}: unknown source {source_id}")
        for locale in ("en", "ar"):
            if not term.terms.get(locale):
                problems.append(f"glossary {term.id}: missing {locale} terms")

    return problems


def _find_cycle(edges: dict[str, set[str]]) -> list[str] | None:
    state: dict[str, int] = {}
    stack: list[str] = []

    def visit(node: str) -> list[str] | None:
        state[node] = 1
        stack.append(node)
        for nxt in sorted(edges.get(node, ())):
            if state.get(nxt) == 1:
                return stack[stack.index(nxt) :] + [nxt]
            if state.get(nxt) is None:
                found = visit(nxt)
                if found:
                    return found
        stack.pop()
        state[node] = 2
        return None

    for node in sorted(edges):
        if state.get(node) is None:
            found = visit(node)
            if found:
                return found
    return None
