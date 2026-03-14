import { test, expect } from "./fixtures";

const emptyAgentsResponse = {
  data: [],
  meta: { page: 1, per_page: 20, total: 0 },
  errors: [],
};

test.describe("Activity Page", () => {
  test("renders activity page with heading", async ({ authedPage: page }) => {
    await page.route("**/api/v1/agents", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(emptyAgentsResponse),
      })
    );
    await page.goto("/activity");
    await expect(page.locator("h1")).toContainText("Activity");
  });

  test("page renders without crash", async ({ authedPage: page }) => {
    await page.goto("/activity");
    await page.waitForTimeout(1000);
    // Any content should be visible — page should not show an unhandled error
    const body = await page.textContent("body");
    expect(body?.length).toBeGreaterThan(0);
    // h1 heading should still be present
    await expect(page.locator("h1")).toBeVisible();
  });

  test("has resource type filter", async ({ authedPage: page }) => {
    await page.route("**/api/v1/agents", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(emptyAgentsResponse),
      })
    );
    await page.goto("/activity");
    await page.waitForTimeout(500);
    // Expect at least one filter control — could be a select or a set of filter buttons
    const hasSelect = await page.locator("select").count();
    const hasFilterButton = await page
      .getByRole("button", { name: /all|agent|filter/i })
      .count();
    expect(hasSelect > 0 || hasFilterButton > 0).toBeTruthy();
  });
});
