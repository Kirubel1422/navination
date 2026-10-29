import { defineConfig, devices } from "@playwright/test";

const LIVE_WEB = "http://localhost:3100";
const MOCK_WEB = "http://localhost:3200";
const API = "http://localhost:8001/api/v1";

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  workers: 1,
  timeout: 90_000,
  expect: { timeout: 15_000 },
  retries: process.env.CI ? 1 : 0,
  reporter: [["list"], ["html", { open: "never" }]],
  use: { trace: "retain-on-failure", screenshot: "only-on-failure" },
  projects: [
    {
      name: "live",
      testMatch: /live\..*\.spec\.ts/,
      use: { ...devices["Desktop Chrome"], baseURL: LIVE_WEB },
    },
    {
      name: "mock",
      testMatch: /mock\..*\.spec\.ts/,
      use: { ...devices["Desktop Chrome"], baseURL: MOCK_WEB },
    },
  ],
  webServer: [
    {
      command: "node e2e/start-api.mjs",
      url: `${API}/health`,
      reuseExistingServer: false,
      timeout: 120_000,
    },
    {
      command: "pnpm exec next dev --port 3100",
      url: LIVE_WEB,
      reuseExistingServer: false,
      timeout: 180_000,
      env: {
        NEXT_PUBLIC_API_BASE_URL: API,
        NEXT_PUBLIC_API_MODE: "live",
        NEXT_DIST_DIR: ".next-e2e-live",
      },
    },
    {
      command: "pnpm exec next dev --port 3200",
      url: MOCK_WEB,
      reuseExistingServer: false,
      timeout: 180_000,
      env: {
        NEXT_PUBLIC_API_BASE_URL: "http://localhost:8999/api/v1",
        NEXT_PUBLIC_API_MODE: "mock",
        NEXT_DIST_DIR: ".next-e2e-mock",
      },
    },
  ],
});
