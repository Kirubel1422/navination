import { expect, test } from "@playwright/test";

// The demo persona: expat parents of a newborn in Umm Al Quwain. The first search offers the
// optional profile, and the plan shows how the answers shaped its stages.

test("personalise before searching, then follow a tailored route map", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: /Welcome a new baby/ }).click();

  const dialog = page.getByTestId("personalize-dialog");
  await expect(dialog).toBeVisible();
  await expect(dialog).toContainText("A few quick answers add, remove and order the stages");
  await dialog.getByRole("radio", { name: "Umm Al Quwain", exact: true }).check();
  await dialog.getByRole("radio", { name: "UAE resident", exact: true }).check();
  await dialog.getByRole("radio", { name: "Parent", exact: true }).check();
  await expect(dialog).toContainText("3 of 4 answered");
  await dialog.getByTestId("personalize-apply").click();

  await expect(page.getByTestId("service-card-birth-registration")).toBeVisible();
  await page.getByTestId("create-plan").click();

  // How the answers shaped the plan.
  const tailored = page.getByTestId("tailored-panel");
  await expect(tailored.getByTestId("tailored-residency_status")).toContainText("UAE resident");
  await expect(tailored.getByTestId("tailored-residency_status")).toContainText("Shapes 3 of your steps");
  await expect(tailored).toContainText("Mabrouk Ma Yak");

  // The route map: stages, stops, tailored marks and what is not needed.
  const map = page.getByTestId("plan-map");
  await expect(map.getByTestId("map-stage-0")).toBeVisible();
  await expect(map.getByTestId("map-tailored")).toHaveCount(3);
  await expect(map.getByTestId("map-stop-newborn-residence-permit")).toHaveAttribute("data-state", "waiting");
  await expect(map.getByTestId("map-skipped")).toContainText("Mabrouk Ma Yak");

  // Selecting a stop shows only that step's details.
  await map.getByTestId("map-stop-newborn-passport-embassy").click();
  const step = page.getByTestId("step-newborn-passport-embassy");
  await expect(step).toBeVisible();
  await expect(step.getByTestId("step-tailored")).toContainText("UAE resident");
  await expect(page.locator('[data-testid^="step-"][id^="step-"]')).toHaveCount(1);

  // Everything is still available as a list.
  await page.getByTestId("view-list").click();
  await expect(page.getByTestId("stage-0")).toBeVisible();
});

test("people can search without personalising", async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("Describe your need").fill("I recently arrived and need my overseas degree recognized");
  await page.getByTestId("search-submit").click();
  await page.getByTestId("personalize-skip").click();
  await expect(page.getByTestId("service-card-mohesr-degree-recognition")).toBeVisible();
  // Asked once per session only.
  await page.getByLabel("Describe your need").first().fill("We just had a baby. What do we need?");
  await page.locator("[data-testid=search-submit]:visible").click();
  await expect(page.getByTestId("personalize-dialog")).toHaveCount(0);
});
