import { expect, test } from "@playwright/test";

import { DEGREE_QUERY } from "./helpers";

test("mock mode is clearly labelled and covers the main flow", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByTestId("demo-indicator")).toContainText("Demo data");
  await page.getByLabel("Describe your need").fill(DEGREE_QUERY);
  await page.getByTestId("search-submit").click();
  await expect(page.getByTestId("service-card-mohesr-degree-recognition")).toBeVisible();
  await page.getByTestId("create-plan").click();
  await expect(page.getByTestId("journey-title")).toBeVisible();
  await page.getByLabel("Your question").fill("What documents do I need?");
  await page.getByTestId("coach-send").click();
  await expect(page.getByTestId("coach-message-assistant")).toBeVisible();
  await expect(page.getByText("Demo data: this is a fixed example answer")).toBeVisible();
  await expect(page.getByTestId("demo-indicator")).toBeVisible();
});

// Next.js keeps visited pages mounted but hidden, so a second search must not show the first
// search's results (regression: a new request after finishing a plan showed the old services).
test("a new search after finishing a plan shows the new results, not the old ones", async ({ page }) => {
  const visible = (testId: string) => page.locator(`[data-testid="${testId}"]:visible`);
  await page.goto("/");
  await page.getByLabel("Describe your need").fill(DEGREE_QUERY);
  await visible("search-submit").click();
  await expect(visible("service-card-mohesr-degree-recognition")).toBeVisible();
  await visible("create-plan").click();
  await expect(visible("journey-title")).toBeVisible();

  await page.getByRole("link", { name: /^NaviNation/ }).click();
  await expect(page).toHaveURL(/\/$/);
  const second = "I need to update my Emirates ID and renew my driving licence";
  await page.locator("textarea:visible").fill(second);
  await visible("search-submit").click();
  await expect(visible("no-match")).toBeVisible();
  await expect(page.locator("[data-testid^=service-card-]:visible")).toHaveCount(0);
  await expect(page.locator("textarea:visible")).toHaveValue(second);
});
