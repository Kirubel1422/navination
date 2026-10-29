import { expect, test } from "@playwright/test";

import { API, BABY_QUERY, DEGREE_QUERY, expectNoHorizontalOverflow, saveProfile, search } from "./helpers";

test("home page shows commonly requested services", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Commonly requested services" })).toBeVisible();
});

test("AI unavailable is reported honestly, without fallback results", async ({ page }) => {
  await page.goto("/");
  await page.route(`${API}/discover`, (route) =>
    route.fulfill({
      status: 503,
      contentType: "application/json",
      body: JSON.stringify({
        error: { code: "SERVICE_UNAVAILABLE", message: "x", details: [], request_id: "req_ai" },
      }),
    }),
  );
  await page.getByLabel("Describe your need").fill(DEGREE_QUERY);
  await page.getByTestId("search-submit").click();
  await expect(page.getByTestId("error-state")).toContainText("The AI assistant is unavailable");
  await expect(page.locator("[data-testid^=service-card-]")).toHaveCount(0);
});

test("guest search shows source-backed cards with the deciding authority", async ({ page }) => {
  await search(page, DEGREE_QUERY);
  await expect(page.getByTestId("interpreted-need")).toContainText("degree recognised");
  // The guide answers directly; there is no "how the AI worked" panel to read through.
  await expect(page.getByText("Interpreted by the AI agent")).toHaveCount(0);
  await expect(page.getByRole("button", { name: /How the AI agent worked/ })).toHaveCount(0);
  const card = page.getByTestId("service-card-mohesr-degree-recognition");
  await expect(card).toContainText("Ministry of Higher Education and Scientific Research");
  await expect(card).toContainText("Who decides");
  await card.getByRole("button", { name: /Sources/ }).click();
  await expect(card.getByTestId("sources-list")).toContainText("Checked by NaviNation");
  await expect(card.getByTestId("sources-list")).toContainText("Page last updated");
  await expect(page.getByTestId("service-card-degree-verification-partner")).toContainText("Needs review");
});

test("ambiguous request asks one clarification with explicit options", async ({ page }) => {
  await search(page, "My certificate from abroad needs to be accepted");
  await expect(page.getByTestId("clarification")).toBeVisible();
  await page.getByRole("radio", { name: /school/i }).check();
  await page.getByTestId("clarification-submit").click();
  await expect(page.getByTestId("service-card-moe-school-equivalency")).toBeVisible();
});

test("unsupported request gets an honest no-match", async ({ page }) => {
  await search(page, "I want to renew my driving licence");
  await expect(page.getByTestId("no-match")).toContainText("won't guess");
  await expect(page.locator("[data-testid^=service-card-]")).toHaveCount(0);
});

test("connection failure shows an error, never fake results", async ({ page }) => {
  await page.goto("/");
  await page.route(`${API}/discover`, (route) => route.abort("failed"));
  await page.getByLabel("Describe your need").fill(DEGREE_QUERY);
  await page.getByTestId("search-submit").click();
  await expect(page.getByTestId("error-state")).toContainText("can't reach NaviNation");
  await expect(page.locator("[data-testid^=service-card-]")).toHaveCount(0);
});

test("optional profile changes guidance with an explanation and can be cleared", async ({ page }) => {
  await search(page, DEGREE_QUERY);
  const card = page.getByTestId("service-card-mohesr-degree-recognition");
  await expect(card).toContainText("More information needed");
  await saveProfile(page, ["Yes, issued outside the UAE"]);
  await expect(page.getByTestId("results-outdated")).toBeVisible();
  await page.getByTestId("update-results").click();
  await expect(page.getByTestId("what-changed")).toContainText("More information needed → May apply to you");
  await expect(card).toContainText("Your profile matches");
  await page.getByTestId("profile-open").click();
  await page.getByTestId("profile-clear").click();
  await expect(page.getByTestId("results-outdated")).toBeVisible();
  await page.getByTestId("update-results").click();
  await expect(card).toContainText("More information needed");
});

test("secondary life event: a new baby", async ({ page }) => {
  await search(page, BABY_QUERY);
  await expect(page.getByTestId("service-card-birth-registration")).toBeVisible();
  await expect(page.getByTestId("service-card-newborn-passport-embassy")).toContainText("Needs review");
  await saveProfile(page, ["UAE resident"]);
  await page.getByTestId("update-results").click();
  await expect(page.getByTestId("service-card-mabrouk-ma-yak")).toContainText("May not match your profile");
});

test("keyboard-only search on a phone-sized screen", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");
  await expect(page.getByLabel("Describe your need")).toBeVisible();
  await page.keyboard.press("Tab");
  await expect(page.getByRole("link", { name: "Skip to main content" })).toBeFocused();
  await page.keyboard.press("Enter");
  await page.keyboard.press("Tab");
  await expect(page.getByLabel("Describe your need")).toBeFocused();
  await page.keyboard.type(DEGREE_QUERY);
  // Then the optional helpers, in reading order: share location, speak, search.
  await page.keyboard.press("Tab");
  await expect(page.getByTestId("location-use")).toBeFocused();
  await page.keyboard.press("Tab");
  await expect(page.getByTestId("voice-search")).toBeFocused();
  await page.keyboard.press("Tab");
  await expect(page.getByTestId("search-submit")).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page.getByTestId("service-card-mohesr-degree-recognition")).toBeVisible();
  await expectNoHorizontalOverflow(page);
});

test("expired session is explained and not silently replaced", async ({ page }) => {
  await search(page, DEGREE_QUERY);
  await expect(page.getByTestId("interpreted-need")).toBeVisible();
  await page.route(`${API}/session`, (route) =>
    route.fulfill({
      status: 401,
      contentType: "application/json",
      body: JSON.stringify({
        error: { code: "SESSION_EXPIRED", message: "expired", details: [], request_id: "req_test" },
      }),
    }),
  );
  await page.reload();
  await expect(page.getByTestId("session-expired")).toBeVisible();
  await expect(page.getByTestId("interpreted-need")).toHaveCount(0);
  await page.unroute(`${API}/session`);
  await page.getByRole("button", { name: "Start a new session" }).click();
  await expect(page.getByLabel("Describe your need")).toBeVisible();
});
