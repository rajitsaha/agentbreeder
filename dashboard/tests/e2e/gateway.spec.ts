import { test, expect, apiOk } from "./fixtures";

const GATEWAY_URL = "/gateway";
const GATEWAY_API_PATTERN = "**/api/v1/gateway/status";

test("renders gateway page", async ({ authedPage: page }) => {
  await page.route(GATEWAY_API_PATTERN, (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: apiOk({ status: "healthy", providers: [] }, 0),
    }),
  );

  await page.goto(GATEWAY_URL);
  await expect(page.getByText(/gateway/i).first()).toBeVisible();
});

test("shows gateway status", async ({ authedPage: page }) => {
  await page.route(GATEWAY_API_PATTERN, (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: apiOk(
        {
          status: "healthy",
          providers: [
            { name: "openai", status: "healthy", latency_ms: 120 },
          ],
        },
        0,
      ),
    }),
  );

  await page.goto(GATEWAY_URL);
  // "healthy" or "Healthy" should appear somewhere on the page (overall status
  // badge or provider row)
  await expect(
    page.getByText("healthy").or(page.getByText("Healthy")).first(),
  ).toBeVisible();
});

test("page renders without crash", async ({ authedPage: page }) => {
  // No mock — let the API call fail or return an error
  await page.goto(GATEWAY_URL);
  await page.waitForTimeout(1000);

  // The page must show something: an error banner, empty state, or skeleton
  await expect(page.locator("body")).not.toBeEmpty();
});
