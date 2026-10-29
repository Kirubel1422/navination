#!/usr/bin/env node
// Cross-platform helper for the FastAPI app (works on Windows, macOS and Linux).
// Usage: node scripts/run-api.mjs <setup|dev|test|lint|contract-check|cleanup|scripted-llm>
import { spawnSync } from "node:child_process";
import { copyFileSync, existsSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const apiDir = join(dirname(fileURLToPath(import.meta.url)), "..", "apps", "api");
const uv = process.env.UV_BIN ?? "uv";
const isWindows = process.platform === "win32";

function run(args) {
  const result = spawnSync(uv, args, { cwd: apiDir, stdio: "inherit", shell: isWindows });
  if (result.error) {
    console.error(`Could not run "${uv}". Install uv: https://docs.astral.sh/uv/getting-started/installation/`);
    process.exit(1);
  }
  if (result.status !== 0) process.exit(result.status ?? 1);
}

const tasks = {
  setup: () => {
    if (!existsSync(join(apiDir, ".env"))) copyFileSync(join(apiDir, ".env.example"), join(apiDir, ".env"));
    run(["sync"]);
    run(["run", "alembic", "upgrade", "head"]);
    run(["run", "python", "-m", "app.cli", "seed"]);
  },
  dev: () => {
    run(["run", "alembic", "upgrade", "head"]);
    run(["run", "python", "-m", "app.cli", "seed"]);
    run(["run", "uvicorn", "app.main:app", "--reload", "--host", "127.0.0.1", "--port", process.env.API_PORT ?? "8000"]);
  },
  test: () => run(["run", "pytest"]),
  lint: () => {
    run(["run", "ruff", "check", "."]);
    run(["run", "ruff", "format", "--check", "."]);
  },
  "contract-check": () => run(["run", "python", "-m", "app.cli", "export-openapi", "--check"]),
  cleanup: () => run(["run", "python", "-m", "app.cli", "cleanup-sessions"]),
  // Scripted OpenAI-compatible TEST model (not an AI) for offline development and e2e tests.
  "scripted-llm": () => run(["run", "uvicorn", "devtools.fake_llm_server:app", "--port", process.env.LLM_PORT ?? "8002"]),
};

const task = tasks[process.argv[2]];
if (!task) {
  console.error(`Unknown task. Use one of: ${Object.keys(tasks).join(", ")}`);
  process.exit(2);
}
task();
