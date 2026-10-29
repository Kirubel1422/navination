# NaviNation

NaviNation is a working prototype for **TDRA Challenge 17 (UAE Hackathon, Youth Track): Intelligent Citizen Service Navigation and Personalization AI Agent**.

A guest describes a need in everyday English or Arabic. An **AI agent** then:

1. **Discovers services.** It interprets the need, reads NaviNation's reviewed catalog through tools, and reads official UAE government websites when needed. It asks one clarifying question if the request is ambiguous, or says honestly that it cannot help. Results are ranked for the person.
2. **Personalises.** It uses the optional profile (emirate, residency status, life stage, where a qualification was issued) to judge relevance, write the reasons, and order services and steps. "Unknown" stays distinct from "no".
3. **Explains every service card.** Cards show purpose, responsible entity, why the service appeared, missing information, criteria, documents, fees and timing (or "Not confirmed"), and sources with check dates. Services the agent found on the web are labelled **"Found by AI on an official website — not reviewed"**.
4. **Generates the journey.** It writes the stages, steps, instructions and preparation checklists for the request and profile. A guard enforces the few officially verified "must happen first" rules; everything else the AI suggests is advisory and never blocks.
5. **Coaches each step.** It researches with tools (step details, catalog, official pages) and answers with citations it is allowed to make. It then hands off to a verified official or support page.

NaviNation is guidance only. It does not decide eligibility, approve documents, collect credentials or submit applications. The responsible entity always decides.

> **An AI model is required.** Every search, plan, assessment and coach answer is produced by the agent, and there is no rule-based fallback. Without a configured model those requests return a clear "AI unavailable" error (HTTP 503). Any **OpenAI-compatible** Chat Completions endpoint with tool calling works: OpenAI, Azure OpenAI, OpenRouter, vLLM, Ollama, LM Studio and others.

## Repository layout

| Path | Contents |
| --- | --- |
| `apps/web` | Next.js 16 App Router frontend (`@navination/web`): TypeScript strict, Tailwind 4, shadcn/ui, TanStack Query, React Hook Form + Zod, MSW mock mode, Vitest, Playwright |
| `apps/api` | FastAPI backend: Pydantic v2, SQLAlchemy 2, Alembic, uv, pytest, Ruff. Contains the agent runtime (`app/agent`), the OpenAI-compatible adapter (`app/providers`) and the reviewed seed knowledge |
| `apps/api/devtools` | **Test-only** scripted OpenAI-compatible model used by automated tests and e2e. Not an AI, and never shipped in the Docker image |
| `contracts/openapi.json` | API contract, version 1.1.0, generated from the running app |
| `contracts/examples` | Synthetic request/response fixtures (produced with the scripted test model) |
| `docs/architecture.md` | Design, agent guardrails, decisions and assumptions |
| `docs/open-data.md` | Government open data used, how it stays current, the navigation-gaps dataset we publish |
| `docs/demo-guide.md` | Demo steps, example inputs, source coverage, 90-day plan |
| `compose.yaml` | One-command Docker setup |

## One-command start with Docker

1. Copy `.env.docker.example` to `.env` and set your model:
   ```bash
   AI_MODEL=<a tool-calling model id>
   AI_API_KEY=<your key>
   # AI_PROVIDER_BASE_URL=https://...   (leave empty for OpenAI; set for other providers)
   # AI_PROVIDER_BASE_URL=http://host.docker.internal:11434/v1   (e.g. Ollama on this machine)
   ```
2. Start everything:
   ```bash
   docker compose up
   ```
3. Open http://localhost:3000. Health check: http://localhost:8000/api/v1/health (`ai_available: true` means the agent is configured).

Notes:

- `docker compose up` always rebuilds from source; unchanged layers are cached.
- The `api` container runs migrations, imports the reviewed seed and deletes expired sessions, then serves on port 8000 as a non-root user. Guest data lives on the `navination-data` volume; `docker compose down -v` deletes it.
- **Ports in use?** Set `NAVINATION_API_PORT` / `NAVINATION_WEB_PORT` in `.env`. The API URL is compiled into the web bundle, and CORS follows the web port automatically.
- **Web search** (optional): set `WEB_SEARCH_PROVIDER=tavily` or `brave` and `WEB_SEARCH_API_KEY`. Without it the agent can still read official pages it knows about.
- On Linux, if you get `permission denied ... docker.sock`, use `sudo docker compose up` or add yourself to the `docker` group.

## Quick start without Docker (Linux, macOS, Windows)

Prerequisites: Node.js 20.9+ (developed on Node 24), pnpm 11 and [uv](https://docs.astral.sh/uv/getting-started/installation/). uv provides Python ≥ 3.12.

```bash
pnpm install
pnpm setup:api                                 # uv sync, create apps/api/.env, migrate, seed
# edit apps/api/.env: AI_MODEL, AI_API_KEY (and AI_PROVIDER_BASE_URL if not OpenAI)
cp apps/web/.env.example apps/web/.env.local
pnpm dev                                       # API on :8000 and web on :3000
```

**No model available?** For UI development only, `node scripts/run-api.mjs scripted-llm` starts the scripted test model on port 8002. Point the API at it with `AI_PROVIDER_BASE_URL=http://127.0.0.1:8002/v1`, `AI_MODEL=scripted-test-model` and `AI_API_KEY=test`. It answers from a fixed keyword script, so **do not demo it as AI**.

### Commands

| Task | Command |
| --- | --- |
| Start both / API / web | `pnpm dev` · `pnpm dev:api` · `pnpm dev:web` |
| Backend tests / lint | `pnpm test:api` · `pnpm lint:api` |
| Migrations | `cd apps/api && uv run alembic upgrade head` |
| Validate / import seed | `cd apps/api && uv run python -m app.cli validate` · `... seed` |
| Delete expired sessions | `node scripts/run-api.mjs cleanup` |
| Contract export / drift check | `cd apps/api && uv run python -m app.cli export-openapi [--check]` |
| Regenerate examples + mock fixtures | `cd apps/api && uv run python scripts/generate_examples.py`, then `pnpm --filter @navination/web mocks:sync` |
| Frontend checks | `pnpm --filter @navination/web lint`, `typecheck`, `test`, `build` |
| Browser tests | `pnpm --filter @navination/web exec playwright install chromium` once, then `pnpm --filter @navination/web test:e2e` |
| Contract + types drift | `pnpm contract:check` |

The Playwright suite starts the scripted test model on port 8002 and the real API on 8001 (fresh SQLite database, web fetching off). The API reaches the scripted model through the real OpenAI-compatible adapter, so the full HTTP agent path is exercised. The suite also starts a live web server on 3100 and a mock-mode web server on 3200.

## Configuration

### Backend (`apps/api/.env`, see `.env.example`)

| Variable | Default | Notes |
| --- | --- | --- |
| `AI_PROVIDER` | `openai_compatible` | `disabled` turns the agent off (every AI request returns 503) |
| `AI_MODEL` | empty | **Required.** A model that supports function/tool calling |
| `AI_API_KEY` | empty | Required unless `AI_PROVIDER_BASE_URL` points to a local server. Backend only |
| `AI_PROVIDER_BASE_URL` | empty (= `https://api.openai.com/v1`) | Any OpenAI-compatible `/v1` URL |
| `AI_TIMEOUT_SECONDS`, `AI_MAX_RETRIES` | `60`, `1` | Per model call |
| `AGENT_MAX_STEPS`, `AGENT_DEADLINE_SECONDS` | `10`, `150` | Budget per agent run (model calls, wall clock) |
| `OFFICIAL_DOMAINS` | `u.ae,gov.ae,tamm.abudhabi,uaepass.ae` | The only hosts (plus their subdomains) the agent may read, cite or link to |
| `WEB_FETCH_ENABLED`, `WEB_FETCH_TIMEOUT_SECONDS` | `true`, `10` | Official-page reading tool |
| `WEB_SEARCH_PROVIDER`, `WEB_SEARCH_API_KEY` | `none` | `tavily` or `brave` for official-site search |
| `DATABASE_URL` | `sqlite:///./data/navination.db` | Or `postgresql+psycopg://user:pass@host:5432/navination` |
| `CORS_ORIGINS` | `http://localhost:3000,http://127.0.0.1:3000` | Exact frontend origins |
| `SESSION_TTL_HOURS` | `24` | Guest session lifetime |
| `*_LIMIT_PER_MINUTE` | 20 sessions, 30 searches, 10 plans, 12 coach messages | In-process rate limits |

### Frontend (`apps/web/.env.local`)

| Variable | Default | Notes |
| --- | --- | --- |
| `NEXT_PUBLIC_API_BASE_URL` | `http://localhost:8000/api/v1` | The browser calls FastAPI directly |
| `NEXT_PUBLIC_API_MODE` | `live` | `mock` serves fixtures from `contracts/examples` with a permanent **Demo data** badge. There is never an automatic fallback to mock data |

## How the agent is kept honest

- **Tools, not memory.** The agent reads the reviewed catalog through tools, and reads official pages only over HTTPS on `OFFICIAL_DOMAINS`. Redirects are re-checked at every hop. Search results are leads only; a page must be fetched before it can be cited.
- **Validated submissions.** Each task ends with a `submit_*` tool call, which is validated against a JSON schema and against provenance rules:
  - catalog IDs must exist;
  - AI-found services, their links and their sources must be pages the agent read in that run;
  - citations must belong to the service, the plan, or pages it read.

  Problems are sent back to the agent to fix.
- **Verified rules guard the plan.** Only officially verified "must happen first" rules can block a step. If the AI orders them wrongly or leaves a prerequisite out, the guard fixes the plan and says why in the plan notes.
- **Safe output.** Unknown URLs are removed from coach answers. Actions can only reference steps in the plan. Handoff links come only from service records, never from model text or the browser.
- **Untrusted input.** User text and page content are passed to the model as data, and prompts tell it to ignore embedded instructions.
- **Bilingual output.** The agent writes English and Arabic at once, so switching language re-renders AI content without another call. Earlier coach messages keep their original language.
- **Honest failure.** No model, timeouts, step-budget exhaustion and invalid output all become HTTP 503 with a clear message. Nothing is invented and nothing falls back to rules.

**What has been verified.** The agent runtime, tools, guard and adapter are covered by automated tests: 133 backend tests, plus 12 browser tests through the real adapter against the scripted test model. **No real model was called during development** because no credentials were provided. Answer quality, latency and cost therefore depend on the model you configure and are unverified. The Tavily and Brave search clients follow their public API documentation and are tested only against mocked responses.

## Data, privacy and sessions

- A guest session is created on first visit. The token is random, stored only as a SHA-256 hash, and kept by the browser in `sessionStorage`. Only the language preference uses `localStorage`.
- The agent receives the request, the four optional profile fields and plan details. It never receives ID numbers, the session token or any credentials. Your model provider processes what is sent, so choose one whose data terms suit you.
- Data lives in the API database: profile, discoveries (with AI output), AI-found service records, journeys, checklists, coach messages and handoff intents. **Clear my session** deletes all of it in one transaction. `cleanup-sessions` removes expired sessions.
- Upgrading to schema 0002 deletes discoveries and plans made by the earlier rule-based version. Sessions and profiles are kept.

## Coverage

The reviewed catalog holds 10 services across two life events: an overseas education qualification and a new baby. Eight are verified against official pages checked on 28 Oct 2026, and two are labelled `needs_review`. With web tools enabled, the agent can go beyond the catalog to services on official UAE sites, and those are always labelled as not reviewed. The 60% discovery-time and 45% adoption targets are goals to evaluate, not results.

## Troubleshooting

- **"The AI assistant is unavailable".** Check `/api/v1/health`. If `ai_available` is `false`, set `AI_MODEL` and `AI_API_KEY` (or `AI_PROVIDER_BASE_URL`). If it is `true`, the model failed or timed out; the API logs show the reason, such as authentication, rate limit or step budget.
- **The model never finishes.** Use a model with reliable tool calling, or raise `AGENT_MAX_STEPS` / `AGENT_DEADLINE_SECONDS`.
- **Port 8000 in use.** Set `NAVINATION_API_PORT` (Docker), or run `API_PORT=8010 NEXT_PUBLIC_API_BASE_URL=http://localhost:8010/api/v1 pnpm dev`.
- **The browser can't reach the API.** Check `NEXT_PUBLIC_API_BASE_URL` and `CORS_ORIGINS`.
