# NaviNation web (`@navination/web`)

Next.js 16 App Router frontend. It calls the FastAPI service directly from the browser. See the root [README](../../README.md).

```bash
cp .env.example .env.local     # NEXT_PUBLIC_API_BASE_URL, NEXT_PUBLIC_API_MODE=live|mock
pnpm dev                       # http://localhost:3000
```

| Script | Purpose |
| --- | --- |
| `dev`, `build`, `start` | Next.js |
| `lint`, `typecheck` | ESLint, `tsc --noEmit` (strict) |
| `test` | Vitest + React Testing Library |
| `test:e2e` | Playwright: real FastAPI on :8001 (fresh DB, no AI key) and live web on :3100, plus mock web on :3200 |
| `api:types` / `api:types:check` | Generate or verify `src/lib/api/schema.gen.ts` from `contracts/openapi.json` (do not edit by hand) |
| `mocks:sync` / `mocks:check` | Generate or verify `src/mocks/fixtures.gen.ts` from `contracts/examples` |

Source layout (`src/`):

- `app/` contains thin route files: `/`, `/discover`, `/services/[serviceId]`, `/journeys/[journeyId]`.
- `components/ui` (shadcn) and `components/layout` hold shared UI.
- `features/{discovery,profile,services,journey,coach}` hold the feature components.
- `lib/api` is the typed client, endpoints and query keys. `lib/session` handles session bootstrap, expiry and storage. `lib/i18n` holds the English and Arabic dictionaries and the locale handling.
- `mocks/` contains the MSW handlers (mock mode only).
- `test/` contains the test setup.
