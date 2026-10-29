# NaviNation architecture and decisions

## Responsibilities

- **FastAPI (`apps/api`)** owns everything with business meaning: guest sessions, the AI agents and their tools, validation of agent output, the verified-rule guard, progress rules, stale-state checks and destination validation.
- **Next.js (`apps/web`)** owns presentation only. It never calls a model or builds a destination URL.

```
Browser ──JSON + Bearer token──▶ FastAPI /api/v1
                                   ├─ modules/sessions    token hash, expiry, profile, context_revision
                                   ├─ modules/discovery   discovery agent → validated results, clarification, no-match
                                   ├─ modules/services    unified registry (catalog + AI-found), assessment agent
                                   ├─ modules/journeys    planning agent → verified-rule guard → persisted plan
                                   ├─ modules/coach       coach agent → citation/URL/action validation
                                   ├─ modules/handoffs    destinations only from service records
                                   ├─ agent/              runtime loop, tools, prompts, submission schemas, official web
                                   ├─ providers/          OpenAI-compatible Chat Completions adapter
                                   └─ knowledge/          reviewed YAML seed → validated → kb_* tables
```

## Agent runtime (`app/agent`)

- **`runtime.run_agent`** is a bounded loop. It sends the conversation plus function-tool specs to the model, executes read-only tool calls, and returns results (or tool errors) to the model.
  - It finishes only when the model calls the run's `submit_*` tool with a submission that passes the Pydantic schema and the semantic checks.
  - Rejected submissions go back to the model with the listed problems.
  - Budgets: `AGENT_MAX_STEPS` model calls and `AGENT_DEADLINE_SECONDS`. If the model replies with plain text, it is reminded to submit, at most twice.
- **Schemas** (`drafts.py`) double as the submit tools' JSON schemas. `$ref`, `$defs` and annotation titles are inlined away so that more compatible servers accept them. All user-facing text is bilingual `{en, ar}`.
- **Tools** (`tools.py`):
  - `list_catalog_services` and `get_catalog_service` expose reviewed records, including profile rules, sources and reviewed dependencies.
  - `fetch_official_page` and, when configured, `search_official_web` expose the official web.
  - The coach also has `get_step`. Every tool call is recorded as an `agent_steps` trace that the UI shows.
- **Official web** (`web.py`):
  - HTTPS only, on `OFFICIAL_DOMAINS` and their subdomains. Credentials in URLs and non-default ports are rejected.
  - Redirects are followed manually and each hop is re-checked. Bodies are capped at 1.5 MB and reduced to ≤ 9,000 characters of text. Pages are cached in process for 6 hours.
  - Search is Tavily or Brave, restricted to the same domains, and results are filtered again.
  - Fetched pages also return their official-domain links (anchor text + URL, up to 40), so the agent navigates instead of guessing URLs.
- **Open data layer** (`app/opendata`, details in [open-data.md](open-data.md)): a daily mirror of the Bayanat and Ajman catalogues, curated dataset snapshots with provenance and bundled fallbacks, service insights personalised to the profile, related datasets, and an anonymous navigation-gaps dataset published back. The agents get the figures as citable `OPEN_DATA`.
- **Open data tools** (`bayanat.py`, `ajman.py`; no keys, switch off with `BAYANAT_ENABLED` / `AJMAN_DATA_ENABLED`). Portals from the HackArena playbook's open-data index (§2.1–2.4), checked 2026-10-29:
  - **Bayanat (federal, FCSC).** `search_bayanat_datasets` replays the portal's own listing request (`POST /DatasetsListing/GetDatasetsListing` with its anti-forgery token); there is no public search API. `get_bayanat_dataset` parses a dataset page (description, entity, resources). `read_bayanat_resource` previews CSV resources through `GET /api/DatasetResources/DownloadSingle?resourceID=` (the portal's Download button). The documented `GET /api/DatasetResources/GetDatasetResource?resourceID={GUID}` returned an empty body for every resource GUID found on dataset pages, so it is not used.
  - **Ajman Data (Department of Digital Ajman).** Opendatasoft Explore API v2.1 at `data.ajman.ae/api/explore/v2.1` (`search_ajman_datasets`, `get_ajman_records`). The playbook's `api.ajman.ae` host does not resolve.
  - **Not integrated:** Data.Dubai needs an API key and secret; the other emirate portals list no open API.
  - Open data is used to identify the responsible entity and add real figures; it is never treated as proof of a service's requirements. Opened Bayanat datasets and returned Ajman datasets are citable like fetched pages.
- **Provider** (`providers/openai_compatible.py`): the official `openai` SDK with function tools and `tool_choice="auto"`. No temperature or token parameters are sent, for compatibility. Every SDK error, `length` or `content_filter` finish becomes `ProviderError`. The registry returns no model unless `AI_MODEL` and a key or base URL are set.
- **Runner** (`runner.py`): maps "no model" and every `AgentError` to `503 SERVICE_UNAVAILABLE` with an honest message. There is deliberately no rule-based fallback.

## The agents

1. **Discovery** (`submit_discovery`). The agent returns `ready` with ranked results, `needs_clarification` with one question and options, or `no_match`.
   - Checks: catalog IDs exist with no duplicates; `kind=web` services carry `source_urls` and an `official_url`/`support_url` that the agent fetched in this run; item citations are among the service's sources; at most one clarification round.
   - AI-found services are stored per session (`ai_services`) as `origin=ai_web`, `verification_status=needs_review`. Their sources are the fetched pages, with the real fetch time as `checked_at`.
   - Assessments (relevance, reasons, missing fields) are stored per service. Citations that do not belong to the service are dropped, and "missing" fields the person already answered are removed.
2. **Assessment** (`submit_assessment`). `GET /services/{id}` reuses the latest assessment made at the current profile revision. Otherwise, for example after a profile change, it asks the agent.
3. **Planning** (`submit_plan`). The agent writes the title, stages, steps (service, title, instructions, per-step assessment, checklist with citations), advisory `depends_on` edges, notices, or `unsupported`.
   - Checks: every selected service appears once; keys are unique; services are known (catalog, this session's AI-found services, or new web services with provenance); `depends_on` points to earlier stages.
   - The **guard** then applies the reviewed rules:
     - a verified required edge whose condition matches the profile becomes a hard dependency, and a missing prerequisite is inserted;
     - dependents are pushed to later stages (the AI's own ordering is kept unless it conflicts);
     - a verified edge whose condition is unknown becomes advisory with a review note;
     - each change is explained in the plan notes.
   - Only hard edges create blockers.
4. **Coach** (`submit_answer`). Context is the plan's steps, the current step in full, the profile, recent history and the question (as data).
   - Citations may be catalog sources, plan sources, or pages fetched in this turn; others are rejected. Grounding claimed without valid citations is downgraded.
   - URLs not known to the system are stripped. Actions must reference plan steps and records that have the link.
   - `client_message_id` and a payload fingerprint make retries idempotent, and failed turns store nothing.

## Persistence (migration `0002_agentic_ai`)

- `discoveries`: bilingual `interpreted_need`, `topic_label`, `notices`, per-service `assessments`, `agent_steps`.
- `ai_services`: session-scoped AI-found service records.
- `journeys.plan`: title, stages, dependencies (by step key), notices (AI and guard), `agent_steps`. Steps hold `key`, `order_group`, bilingual `title`/`instructions`, `checklist` (`{id, text, source_ids, ai_generated}`) and `assessment`.
- `coach_messages.web_citations`.
- Stale plans render exactly as generated, from their snapshot. Replanning calls the planner again with the previous plan, so step keys and checklist wording stay stable. Step progress is kept when the service and its hard prerequisites are unchanged, and checklist answers are kept when an item's wording is unchanged. Otherwise progress is reset and explained.

## Contract changes (1.0.0 → 1.1.0, additive)

- `Service.origin`
- `Discovery.agent_steps`
- `Journey.stages`, `Journey.agent_steps`
- `JourneyStep.title`, `instructions`, `checklist`
- `CoachTurn.agent_steps`
- `Health.web_search_available`

`mode` is always `"ai"`. `document_progress` IDs now refer to checklist items.

## Deliberate departures from the original specification (requested change)

The original brief required:

- a deterministic, rule-based mode that works without paid credentials;
- plans built from a reviewed dependency graph rather than model output;
- reviewed knowledge only.

At the product owner's request these were replaced:

- every request is handled by an AI agent;
- plans are AI-generated, with only verified rules acting as hard constraints;
- the agent may use official UAE websites.

The safeguards kept from the original are provenance checks, official-domain-only fetching and links, needs-review labelling of AI-found services, user text treated as data, and honest 503s instead of invented content.

Automated tests use `devtools/scripted_model.py`, a deterministic stand-in that speaks the same tool protocol. It is excluded from the Docker image and must not be presented as AI.

## Assumptions and limits

- Rate limits and the page cache are per process; use shared stores for multiple instances.
- Real-model quality, latency and cost are unverified (no credentials were available). Small or local models may fail the tool protocol; the result is a 503, never a wrong silent answer.
- Arabic output quality depends on the model; Arabic seed content should be reviewed by a native speaker.
- Official pages that render only with JavaScript cannot be read by the fetcher. The agent gets a clear tool error and can try other pages.
- Next.js 16.4 `cacheComponents`/`partialPrefetching` stay enabled. Pages render private, client-fetched data and opt out of instant-navigation validation.
