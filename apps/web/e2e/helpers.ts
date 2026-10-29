import { expect, type Page } from "@playwright/test";

export const API = "http://localhost:8001/api/v1";
export const DEGREE_QUERY = "I recently arrived and need my overseas degree recognized";
export const BABY_QUERY = "We just had a baby. What do we need to register?";

/**
 * Flows that do not test personalisation start as if the "make your plan fit you" prompt was
 * already answered, and read plans in the list view (the persona spec covers the dialog and map).
 */
export async function classicFlow(page: Page) {
  await page.addInitScript(() => {
    window.sessionStorage.setItem("navination.personalizePrompted", "true");
    window.sessionStorage.setItem("navination.planView", JSON.stringify("list"));
  });
}

export async function search(page: Page, query: string) {
  await page.goto("/");
  await page.getByLabel("Describe your need").fill(query);
  await page.getByTestId("search-submit").click();
}

export async function saveProfile(page: Page, choices: string[]) {
  await page.getByTestId("profile-open").click();
  for (const name of choices) {
    await page.getByRole("radio", { name, exact: true }).check();
  }
  await page.getByTestId("profile-save").click();
  await expect(page.getByRole("dialog")).toBeHidden();
}

export async function setProgress(page: Page, serviceId: string, option: string) {
  await page.getByTestId(`progress-${serviceId}`).click();
  await page.getByRole("option", { name: option }).click();
}

export async function token(page: Page): Promise<string> {
  return page.evaluate(() => JSON.parse(window.sessionStorage.getItem("navination.token") ?? "null"));
}

export async function expectNoHorizontalOverflow(page: Page) {
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(overflow).toBeLessThanOrEqual(1);
}
