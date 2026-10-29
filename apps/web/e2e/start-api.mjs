// Starts the real FastAPI app for browser tests: fresh SQLite DB, migrations and seed.
// The AI agent talks to devtools/fake_llm_server (a scripted OpenAI-compatible test model)
// through the real OpenAI-compatible adapter. Web fetching is off so tests never hit real sites.
import { spawn, spawnSync } from "node:child_process";
import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const apiDir = join(dirname(fileURLToPath(import.meta.url)), "../../api");
const dbDir = mkdtempSync(join(tmpdir(), "navination-e2e-"));
const port = process.env.E2E_API_PORT ?? "8001";
const llmPort = process.env.E2E_LLM_PORT ?? "8002";
const env = {
  ...process.env,
  DATABASE_URL: `sqlite:///${join(dbDir, "e2e.db")}`,
  CORS_ORIGINS: process.env.E2E_WEB_ORIGINS ?? "http://localhost:3100,http://127.0.0.1:3100",
  AI_PROVIDER: "openai_compatible",
  AI_PROVIDER_BASE_URL: `http://127.0.0.1:${llmPort}/v1`,
  AI_MODEL: "scripted-test-model",
  AI_API_KEY: "e2e-test",
  WEB_FETCH_ENABLED: "false",
  WEB_SEARCH_PROVIDER: "none",
  BAYANAT_ENABLED: "false",
  AJMAN_DATA_ENABLED: "false",
  PLACES_ENABLED: "false",
  OPEN_DATA_SYNC: "false",
  APP_ENV: "test",
  SESSION_CREATE_LIMIT_PER_MINUTE: "1000",
  COACH_LIMIT_PER_MINUTE: "1000",
  DISCOVER_LIMIT_PER_MINUTE: "1000",
  PLAN_LIMIT_PER_MINUTE: "1000",
};
const uv = process.env.UV_BIN ?? "uv";
for (const args of [["run", "alembic", "upgrade", "head"], ["run", "python", "-m", "app.cli", "seed"]]) {
  const result = spawnSync(uv, args, { cwd: apiDir, env, stdio: "inherit" });
  if (result.status !== 0) process.exit(result.status ?? 1);
}
const llm = spawn(uv, ["run", "uvicorn", "devtools.fake_llm_server:app", "--port", llmPort], {
  cwd: apiDir,
  env,
  stdio: "inherit",
});
const server = spawn(uv, ["run", "uvicorn", "app.main:app", "--port", port], { cwd: apiDir, env, stdio: "inherit" });
const stop = () => {
  server.kill("SIGTERM");
  llm.kill("SIGTERM");
};
process.on("SIGTERM", stop);
process.on("SIGINT", stop);
server.on("exit", (code) => {
  llm.kill("SIGTERM");
  process.exit(code ?? 0);
});
