import { expect, test } from "@playwright/test";

import { API, DEGREE_QUERY, expectNoHorizontalOverflow, saveProfile, search, setProgress, token } from "./helpers";

test("full demonstration journey against the real API", async ({ page, request }) => {
  // Discover and personalise.
  await search(page, DEGREE_QUERY);
  await saveProfile(page, ["UAE resident", "Yes, issued outside the UAE"]);
  await page.getByTestId("update-results").click();
  await expect(page.getByTestId("service-card-mohesr-degree-recognition")).toContainText("May apply to you");

  // Plan with reviewed prerequisites and parallel tasks. UAE PASS is deselected on purpose:
  // the planner must add it back as a verified required prerequisite and explain why.
  await page.getByTestId("select-uae-pass-account").click();
  await expect(page.getByTestId("select-uae-pass-account")).not.toBeChecked();
  await page.getByTestId("create-plan").click();
  await expect(page.getByTestId("journey-title")).toContainText("Plan:");
  await expect(page.getByTestId("journey-notices")).toContainText('Added "Set up UAE PASS');
  await expect(page.getByTestId("stage-0")).toContainText("These steps can be done at the same time.");
  await expect(page.getByTestId("stage-0")).toContainText("Get ready");
  const mofa = page.getByTestId("step-mofa-attestation-abroad");
  await expect(mofa.getByTestId("availability")).toContainText("Waiting for an earlier step");

  // Document checklist and user-reported progress.
  await expect(mofa.getByTestId("step-instructions")).toBeVisible();
  const firstDoc = mofa.locator('[data-testid^="doc-"]').first();
  await firstDoc.getByRole("radio", { name: "I have it" }).click();
  await expect(firstDoc.getByRole("radio", { name: "I have it" })).toBeChecked();
  await setProgress(page, "mofa-attestation-abroad", "Done (as reported by you)");
  await expect(mofa.getByTestId("step-error")).toContainText("Finish the required earlier steps");
  await setProgress(page, "uae-pass-account", "Done (as reported by you)");
  await expect(mofa.getByTestId("availability")).toContainText("Ready to prepare");
  await setProgress(page, "mofa-attestation-abroad", "In progress");
  await expect(page.getByTestId("progress-mofa-attestation-abroad")).toContainText("In progress");

  // Coach: grounded answer with citations; failed send retried with the same client_message_id.
  await mofa.getByTestId("ask-coach-mofa-attestation-abroad").click();
  await expect(page.getByTestId("coach-context")).toContainText("Attest a document issued outside the UAE");
  const bodies: string[] = [];
  page.on("request", (req) => {
    if (req.url().endsWith("/coach") && req.method() === "POST") bodies.push(req.postData() ?? "");
  });
  let failNext = true;
  await page.route(`${API}/journeys/*/coach`, (route) => {
    if (failNext) {
      failNext = false;
      return route.abort("failed");
    }
    return route.continue();
  });
  await page.getByLabel("Your question").fill("What documents do I need?");
  await page.getByTestId("coach-send").click();
  await expect(page.getByTestId("coach-failed")).toBeVisible();
  await page.getByRole("button", { name: "Retry sending" }).click();
  const reply = page.getByTestId("coach-message-assistant").last();
  await expect(reply).toContainText("original document");
  await expect(reply.getByTestId("coach-citations")).toBeVisible();
  // Navi answers like a person: no "AI mode" badge on the reply.
  await expect(reply).toContainText("Navi");
  await expect(reply.getByTestId("coach-mode")).toHaveCount(0);
  expect(bodies).toHaveLength(2);
  expect(JSON.parse(bodies[0]).client_message_id).toBe(JSON.parse(bodies[1]).client_message_id);
  await page.unroute(`${API}/journeys/*/coach`);

  // Verified official handoff, and an honest unavailable destination.
  await page.getByTestId("handoff-official-mohesr-degree-recognition").click();
  const ready = page.getByTestId("step-mohesr-degree-recognition").getByTestId("handoff-ready");
  const link = ready.getByRole("link");
  await expect(link).toHaveAttribute("href", /^https:\/\/www\.mohesr\.gov\.ae\//);
  await expect(link).toHaveAttribute("target", "_blank");
  await expect(link).toHaveAttribute("rel", /noopener/);
  await expect(ready).toContainText("does not start or submit an application");
  await page.getByTestId("handoff-official-degree-verification-partner").click();
  await expect(page.getByTestId("handoff-unavailable")).toContainText("verified");

  // Refresh recovers the same session, plan and conversation.
  const url = page.url();
  await page.reload();
  await expect(page).toHaveURL(url);
  await expect(page.getByTestId("progress-uae-pass-account")).toContainText("Done");
  await expect(page.getByTestId("coach-message-assistant")).toHaveCount(1);
  await page.goto("/");
  await expect(page.getByTestId("resume-card")).toBeVisible();
  await page.getByRole("link", { name: "Open my plan" }).click();
  await expect(page).toHaveURL(url);

  // Profile change makes the plan stale; replanning is explicit and keeps valid progress.
  await page.getByTestId("profile-open").click();
  await page.getByRole("radio", { name: "Dubai", exact: true }).check();
  await page.getByTestId("profile-save").click();
  await expect(page.getByTestId("stale-banner")).toBeVisible();
  await expect(page.getByTestId("progress-uae-pass-account")).toBeDisabled();
  await expect(page.getByText("Update your plan to ask the coach again.")).toBeVisible();
  await page.getByTestId("replan").click();
  await expect(page.getByTestId("stale-banner")).toHaveCount(0);
  await expect(page.getByTestId("journey-notices")).toContainText("Kept your progress");

  // Arabic: direction, localized structured content and new coach replies.
  await page.getByTestId("language-toggle").click();
  await expect(page.locator("html")).toHaveAttribute("dir", "rtl");
  await expect(page.locator("html")).toHaveAttribute("lang", "ar");
  await expect(page.getByTestId("journey-title")).toContainText("خطتك");
  await expect(page.getByTestId("stage-0")).toContainText("الاستعداد");
  await page.getByLabel("سؤالك").fill("ما هي الرسوم؟");
  await page.getByTestId("coach-send").click();
  await expect(page.getByTestId("coach-message-assistant").last()).toContainText("الرسوم");
  await expect(page.getByTestId("coach-message-assistant").first()).toContainText("original document");
  await page.setViewportSize({ width: 390, height: 844 });
  await expectNoHorizontalOverflow(page);
  await page.getByTestId("language-toggle").click();
  await expect(page.locator("html")).toHaveAttribute("dir", "ltr");

  // Clearing the session invalidates the token and its saved data.
  const oldToken = await token(page);
  const journeyId = decodeURIComponent(url.split("/journeys/")[1]);
  await page.getByTestId("clear-session-open").click();
  await page.getByTestId("clear-session-confirm").click();
  await expect(page.getByTestId("session-cleared")).toBeVisible();
  const auth = { Authorization: `Bearer ${oldToken}` };
  expect((await request.get(`${API}/session`, { headers: auth })).status()).toBe(401);
  expect((await request.get(`${API}/journeys/${journeyId}`, { headers: auth })).status()).toBe(401);
});
