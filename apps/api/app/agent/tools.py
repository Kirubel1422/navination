"""Read-only tools shared by the agents."""

from datetime import UTC, datetime
from typing import Any

from app.agent import contacts
from app.agent.ajman import AjmanData, AjmanError
from app.agent.bayanat import Bayanat, BayanatError
from app.agent.places import EMIRATE_CENTRES, Places, PlacesError
from app.agent.runtime import AgentContext, Tool, ToolError, WebSource
from app.agent.web import OfficialWeb, WebError, host_of
from app.core.timeutil import iso
from app.knowledge.repository import Knowledge


def _obj(properties: dict[str, Any], required: list[str]) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": properties,
        "required": required,
        "additionalProperties": False,
    }


def catalog_summary(kb: Knowledge) -> dict[str, Any]:
    return {
        "life_events": [
            {"life_event_id": e.id, "label": e.label["en"]} for e in kb.life_events.values()
        ],
        "services": [
            {
                "service_id": s.id,
                "title": s.title["en"],
                "summary": s.summary["en"],
                "entity": s.entity["en"],
                "life_event_ids": s.life_event_ids,
                "verification_status": s.verification_status,
            }
            for s in sorted(kb.services.values(), key=lambda x: x.position)
        ],
    }


def _short(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def compact_service(kb: Knowledge, service_id: str, with_documents: bool = False) -> dict[str, Any]:
    """A token-lean view of one reviewed service: enough to judge fit and to cite sources."""
    s = kb.services[service_id]
    out: dict[str, Any] = {
        "service_id": s.id,
        "title": s.title["en"],
        "title_ar": s.title["ar"],
        "summary": _short(s.summary["en"], 220),
        "entity": s.entity["en"],
        "life_event_ids": s.life_event_ids,
        "status": s.verification_status,
        "criteria": [
            {
                "text": _short(c.text["en"], 170),
                "source_ids": c.source_ids,
                **({"rule": {"field": c.rule["field"], "allowed": c.rule["in"]}} if c.rule else {}),
            }
            for c in s.criteria
        ],
        "source_ids": s.source_ids,
    }
    if with_documents:
        out["documents"] = [
            {"text": _short(d.text["en"], 170), "source_ids": d.source_ids} for d in s.documents
        ]
        out["fee"] = s.fee_text["en"] if s.fee_text else None
        out["processing_time"] = s.processing_time_text["en"] if s.processing_time_text else None
    return out


def compact_catalog(kb: Knowledge) -> dict[str, Any]:
    """The whole reviewed catalog in one compact block, so most tasks need a single model call."""
    return {
        "life_events": [{"id": e.id, "label": e.label["en"]} for e in kb.life_events.values()],
        "services": [
            compact_service(kb, s.id)
            for s in sorted(kb.services.values(), key=lambda x: x.position)
        ],
    }


def catalog_detail(kb: Knowledge, service_id: str) -> dict[str, Any]:
    service = kb.services.get(service_id)
    if service is None:
        raise ToolError(f"Unknown catalog service_id {service_id!r}. Use list_catalog_services.")
    deps = [d for d in kb.dependencies if service_id in (d.from_service_id, d.to_service_id)]
    return {
        "service_id": service.id,
        "title": {"en": service.title["en"], "ar": service.title["ar"]},
        "summary": service.summary["en"],
        "entity": service.entity["en"],
        "jurisdiction": service.jurisdiction["en"],
        "deciding_authority": service.authority["en"],
        "verification_status": service.verification_status,
        "criteria": [
            {
                "text": c.text["en"],
                "source_ids": c.source_ids,
                "profile_rule": (
                    {"field": c.rule["field"], "allowed_values": c.rule["in"]} if c.rule else None
                ),
            }
            for c in service.criteria
        ],
        "documents": [
            {"text": d.text["en"], "source_ids": d.source_ids} for d in service.documents
        ],
        "fee_text": service.fee_text["en"] if service.fee_text else None,
        "processing_time_text": (
            service.processing_time_text["en"] if service.processing_time_text else None
        ),
        "has_official_url": bool(service.official_url),
        "has_support_url": bool(service.support_url),
        "profile_hints": [
            {"field": h["field"], "values": {k: v["en"] for k, v in h["values"].items()}}
            for h in service.profile_hints
        ],
        "sources": [
            {
                "source_id": sid,
                "title": kb.sources[sid].title["en"],
                "publisher": kb.sources[sid].publisher["en"],
                "verification_status": kb.sources[sid].verification_status,
                "checked_at": iso(kb.sources[sid].checked_at),
            }
            for sid in service.source_ids
        ],
        "reviewed_dependencies": [
            {
                "prerequisite_service_id": d.from_service_id,
                "dependent_service_id": d.to_service_id,
                "kind": d.kind,
                "applies_when": d.condition,
                "explanation": d.explanation["en"],
            }
            for d in deps
        ],
    }


def catalog_tools(kb: Knowledge, ctx: AgentContext) -> list[Tool]:
    def list_services(_: dict[str, Any]) -> Any:
        ctx.record("list_catalog_services", f"{len(kb.services)} reviewed services")
        return catalog_summary(kb)

    def get_service(args: dict[str, Any]) -> Any:
        service_id = str(args.get("service_id", ""))
        detail = catalog_detail(kb, service_id)
        ctx.record("get_catalog_service", service_id)
        return detail

    return [
        Tool(
            "list_catalog_services",
            "List NaviNation's reviewed catalog of UAE government services and life events.",
            _obj({}, []),
            list_services,
        ),
        Tool(
            "get_catalog_service",
            "Full reviewed details of one catalog service: criteria (with profile rules), "
            "documents, fees, timing, sources (cite their source_id) and reviewed dependencies.",
            _obj({"service_id": {"type": "string"}}, ["service_id"]),
            get_service,
        ),
    ]


def glossary_tool(kb: Knowledge, ctx: AgentContext) -> Tool:
    def glossary(_: dict[str, Any]) -> Any:
        ctx.record("list_glossary", f"{len(kb.glossary)} reviewed terms")
        return {
            "terms": [
                {
                    "terms": g.terms.get("en", []),
                    "definition": g.definition["en"],
                    "source_ids": g.source_ids,
                }
                for g in kb.glossary
            ]
        }

    return Tool(
        "list_glossary",
        "Reviewed plain-language definitions of terms such as attestation, recognition, "
        "equalisation, UAE PASS and sponsor, each with citable source_ids.",
        _obj({}, []),
        glossary,
    )


def _remember(ctx: AgentContext, url: str, page: Any) -> None:
    source = WebSource(
        url=page.url, title=page.title, publisher=host_of(page.url), fetched_at=page.fetched_at
    )
    ctx.read_pages[url] = ctx.read_pages[page.url] = source
    ctx.page_texts[url] = ctx.page_texts[page.url] = page.full_text or page.text


def contacts_tool(web: OfficialWeb, ctx: AgentContext) -> Tool:
    def find(args: dict[str, Any]) -> Any:
        url = str(args.get("url", "")).strip()
        try:
            page = web.fetch(url)
        except WebError as exc:
            ctx.record("find_contacts", f"failed: {host_of(url) or url[:60]}")
            raise ToolError(str(exc)) from exc
        _remember(ctx, url, page)
        text = page.full_text or page.text
        phones = contacts.extract(text)
        ctx.record("find_contacts", f"{page.url} ({len(phones)} numbers)")
        return {
            "url": page.url,
            "title": page.title,
            "phones": phones,
            "emails": contacts.emails(text),
            "links": [
                {"text": t, "url": u}
                for t, u in page.links
                if any(
                    w in (t + u).lower()
                    for w in ("contact", "call", "support", "help", "تواصل", "اتصل")
                )
            ][:10],
        }

    return Tool(
        "find_contacts",
        "Read an official page (e.g. an entity's 'Contact us' page) and list the phone numbers and "
        "emails published on it, each with surrounding words, plus links to other contact pages. "
        "Only numbers from these results may be given to the person (copy them exactly).",
        _obj({"url": {"type": "string"}}, ["url"]),
        find,
    )


def places_tool(places: Places, ctx: AgentContext) -> Tool:
    def find(args: dict[str, Any]) -> Any:
        query = str(args.get("query", "")).strip()
        near = ctx.location or EMIRATE_CENTRES.get(ctx.emirate or "", EMIRATE_CENTRES["dubai"])
        try:
            found = places.search(query, near, ctx.location)
        except PlacesError as exc:
            ctx.record("find_service_centers", f"failed: {query[:60]}")
            raise ToolError(str(exc)) from exc
        for place in found:
            ctx.places[place.id] = place
        ctx.record("find_service_centers", f"{query[:80]} ({len(found)} places)")
        return {
            "near": "the person's location"
            if ctx.location
            else f"{ctx.emirate or 'dubai'} (no location shared)",
            "places": [
                {
                    "place_id": p.id,
                    "name": p.name,
                    "kind": p.kind,
                    "address": p.address,
                    "distance_km": p.distance_km,
                }
                for p in found
            ],
        }

    return Tool(
        "find_service_centers",
        "Find physical centres near the person on OpenStreetMap, nearest first. Query with the "
        "centre's common name, e.g. 'Tasheel', 'Amer', 'Tadbeer', 'Emirates ID', 'typing center', "
        "'Customer Happiness Center', 'ICP'. Try 2-3 names; results can include unrelated places, "
        "so return only centres that really match the service.",
        _obj({"query": {"type": "string"}}, ["query"]),
        find,
    )


def web_tools(web: OfficialWeb, ctx: AgentContext) -> list[Tool]:
    def fetch(args: dict[str, Any]) -> Any:
        url = str(args.get("url", "")).strip()
        try:
            page = web.fetch(url)
        except WebError as exc:
            ctx.record("fetch_official_page", f"failed: {host_of(url) or url[:60]}")
            raise ToolError(str(exc)) from exc
        _remember(ctx, url, page)
        ctx.record("fetch_official_page", page.url)
        return {
            "url": page.url,
            "title": page.title,
            "text": page.text,
            "links": [{"text": text, "url": url} for text, url in page.links],
        }

    tools = [
        Tool(
            "fetch_official_page",
            "Read an official UAE government web page (HTTPS on "
            + ", ".join(web.domains)
            + "). Only pages read with this tool may be cited or linked.",
            _obj({"url": {"type": "string"}}, ["url"]),
            fetch,
        )
    ]
    if web.search_available:

        def search(args: dict[str, Any]) -> Any:
            query = str(args.get("query", ""))[:300]
            try:
                hits = web.search(query)
            except WebError as exc:
                raise ToolError(str(exc)) from exc
            ctx.record("search_official_web", query)
            return {
                "results": [{"title": h.title, "url": h.url, "snippet": h.snippet} for h in hits]
            }

        tools.insert(
            0,
            Tool(
                "search_official_web",
                "Search official UAE government websites. Results are leads: fetch a page "
                "before citing it.",
                _obj({"query": {"type": "string"}}, ["query"]),
                search,
            ),
        )
    return tools if web.fetch_enabled else []


def _cite(ctx: AgentContext, url: str, title: str, publisher: str) -> None:
    """Open-data pages read through a portal API count as fetched pages: they may be cited."""
    ctx.read_pages[url] = WebSource(
        url=url,
        title=title or publisher,
        publisher=publisher,
        fetched_at=datetime.now(UTC).replace(microsecond=0),
    )


def bayanat_tools(bayanat: Bayanat, ctx: AgentContext) -> list[Tool]:
    def search(args: dict[str, Any]) -> Any:
        query = str(args.get("query", "")).strip()
        try:
            total, datasets = bayanat.search(query)
        except BayanatError as exc:
            ctx.record("search_bayanat_datasets", f"failed: {query[:60]}")
            raise ToolError(str(exc)) from exc
        ctx.record("search_bayanat_datasets", f"{query[:80]} ({total} datasets)")
        return {
            "total_matches": total,
            "datasets": [
                {
                    "title": d.title,
                    "publishing_entity": d.entity,
                    "last_updated": d.last_updated,
                    "url": d.url,
                }
                for d in datasets
            ],
        }

    def dataset(args: dict[str, Any]) -> Any:
        url = str(args.get("url", "")).strip()
        try:
            detail = bayanat.dataset(url)
        except BayanatError as exc:
            ctx.record("get_bayanat_dataset", "failed")
            raise ToolError(str(exc)) from exc
        _cite(ctx, detail.url, detail.title, "bayanat.ae")
        ctx.record("get_bayanat_dataset", detail.title)
        return {
            "url": detail.url,
            "title": detail.title,
            "publishing_entity": detail.entity,
            "description": detail.description,
            "resources": [
                {"resource_id": r.resource_id, "name": r.name, "format": r.format}
                for r in detail.resources
            ],
        }

    def resource(args: dict[str, Any]) -> Any:
        resource_id = str(args.get("resource_id", "")).strip()
        try:
            preview = bayanat.resource(resource_id)
        except BayanatError as exc:
            ctx.record("read_bayanat_resource", "failed")
            raise ToolError(str(exc)) from exc
        ctx.record("read_bayanat_resource", f"{preview.get('row_count', '?')} rows")
        return preview

    return [
        Tool(
            "search_bayanat_datasets",
            "Search bayanat.ae, the UAE federal open-data portal (3,500+ datasets from ministries "
            "and authorities). Use short English keywords (e.g. 'golden visa', 'marriage'). "
            "Results show which government entity publishes data on a topic, i.e. who is "
            "responsible for it.",
            _obj({"query": {"type": "string"}}, ["query"]),
            search,
        ),
        Tool(
            "get_bayanat_dataset",
            "Open a bayanat dataset (url from search_bayanat_datasets): description, publishing "
            "entity and resources with resource_id and format. After this the dataset url may "
            "be cited.",
            _obj({"url": {"type": "string"}}, ["url"]),
            dataset,
        ),
        Tool(
            "read_bayanat_resource",
            "Read the data of a CSV resource from get_bayanat_dataset: columns, row count and "
            "the first rows. Use it for real figures (e.g. volumes per emirate or year).",
            _obj({"resource_id": {"type": "string"}}, ["resource_id"]),
            resource,
        ),
    ]


def ajman_tools(ajman: AjmanData, ctx: AgentContext) -> list[Tool]:
    def search(args: dict[str, Any]) -> Any:
        query = str(args.get("query", "")).strip()
        try:
            total, datasets = ajman.search(query)
        except AjmanError as exc:
            ctx.record("search_ajman_datasets", f"failed: {query[:60]}")
            raise ToolError(str(exc)) from exc
        for d in datasets:
            _cite(ctx, d.url, d.title, f"Ajman Data ({d.publisher})" if d.publisher else "")
        ctx.record("search_ajman_datasets", f"{query[:80]} ({total} datasets)")
        return {
            "total_matches": total,
            "datasets": [
                {
                    "dataset_id": d.dataset_id,
                    "title": d.title,
                    "publishing_entity": d.publisher,
                    "description": d.description,
                    "records": d.records_count,
                    "last_modified": d.modified,
                    "url": d.url,
                }
                for d in datasets
            ],
        }

    def records(args: dict[str, Any]) -> Any:
        dataset_id = str(args.get("dataset_id", "")).strip()
        try:
            result = ajman.records(dataset_id, str(args.get("query") or ""))
        except AjmanError as exc:
            ctx.record("get_ajman_records", "failed")
            raise ToolError(str(exc)) from exc
        ctx.record("get_ajman_records", f"{dataset_id} ({result['total_records']} records)")
        return result

    return [
        Tool(
            "search_ajman_datasets",
            "Search Ajman Data (data.ajman.ae), the Ajman government open-data portal: datasets "
            "from Ajman entities (municipality, economic development, ports, free zones...). "
            "Use for Ajman-specific needs. Returned dataset urls may be cited.",
            _obj({"query": {"type": "string"}}, ["query"]),
            search,
        ),
        Tool(
            "get_ajman_records",
            "Read records of an Ajman dataset (dataset_id from search_ajman_datasets), "
            "optionally filtered by a full-text query.",
            _obj(
                {"dataset_id": {"type": "string"}, "query": {"type": "string"}},
                ["dataset_id"],
            ),
            records,
        ),
    ]
