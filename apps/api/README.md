# NaviNation API (`apps/api`)

FastAPI service for discovery, rule screening, journey planning, coaching and verified handoffs. See the root [README](../../README.md) for the full setup and [docs/architecture.md](../../docs/architecture.md) for design details.

```bash
cp .env.example .env                 # Windows: copy .env.example .env
uv sync                              # Python + locked dependencies (uv.lock)
uv run alembic upgrade head          # create/upgrade the schema
uv run python -m app.cli seed        # validate + import reviewed knowledge (idempotent)
uv run uvicorn app.main:app --reload --port 8000
```

| Task | Command |
| --- | --- |
| Tests | `uv run pytest` |
| Lint / format check | `uv run ruff check .` · `uv run ruff format --check .` |
| Validate seed only | `uv run python -m app.cli validate` |
| Delete expired sessions | `uv run python -m app.cli cleanup-sessions` |
| Export contract / check drift | `uv run python -m app.cli export-openapi` · `--check` |
| Regenerate examples | `uv run python scripts/generate_examples.py` |
| New migration after model changes | `uv run alembic revision --autogenerate -m "..."` then review it |

Layout: `app/main.py` (app factory), `app/core` (config, errors, middleware, i18n, rate limit), `app/db` (models, engine), `app/knowledge` (YAML seed, validation, import, cached snapshot), `app/modules/{sessions,discovery,services,journeys,coach,handoffs}` (schemas, services, routers), `app/agent` (agent runtime, tools, prompts, submission schemas, official-web fetcher), `app/providers` (OpenAI-compatible adapter, registry), `devtools/` (test-only scripted model and fake OpenAI-compatible server; excluded from the Docker image), `alembic/` (migrations), `tests/`.

PostgreSQL: set `DATABASE_URL=postgresql+psycopg://user:pass@host:5432/navination` (the `psycopg` driver is included), then run the same migrate and seed commands.

Tests need no network access or AI key: they run the real agent loop against `devtools/scripted_model.py` (a deterministic stand-in, not an AI), and the OpenAI-compatible adapter is exercised with a stub HTTP transport. Configure a real model in `.env` (`AI_MODEL`, `AI_API_KEY`, optional `AI_PROVIDER_BASE_URL`) to run the app.
