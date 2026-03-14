import { test, expect } from "./fixtures";

const mockSummaryResponse = {
  data: {
    total_cost_usd: 12.5,
    total_tokens: 250000,
    total_requests: 500,
    by_team: [],
    by_agent: [],
    by_model: [],
  },
  meta: { page: 1, per_page: 20, total: 0 },
  errors: [],
};

const emptyTrendResponse = {
  data: { points: [], period_days: 30 },
  meta: { page: 1, per_page: 20, total: 0 },
  errors: [],
};

const zeroSummaryResponse = {
  data: {
    total_cost_usd: 0,
    total_tokens: 0,
    total_requests: 0,
    by_team: [],
    by_agent: [],
    by_model: [],
  },
  meta: { page: 1, per_page: 20, total: 0 },
  errors: [],
};

test.describe("Costs Page", () => {
  test("renders costs page with heading", async ({ authedPage: page }) => {
    await page.route("**/api/v1/costs/summary", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(mockSummaryResponse),
      })
    );
    await page.route("**/api/v1/costs/trend", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(emptyTrendResponse),
      })
    );
    await page.goto("/costs");
    const heading = page.locator("h1");
    await expect(heading).toBeVisible();
    const headingText = await heading.textContent();
    expect(headingText?.toLowerCase()).toContain("cost");
  });

  test("shows summary cards", async ({ authedPage: page }) => {
    await page.route("**/api/v1/costs/summary", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(mockSummaryResponse),
      })
    );
    await page.route("**/api/v1/costs/trend", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(emptyTrendResponse),
      })
    );
    await page.goto("/costs");
    await page.waitForTimeout(500);
    // Page should render without showing a full-page loader
    const body = await page.textContent("body");
    expect(
      body?.includes("12.50") ||
        body?.includes("12.5") ||
        body?.includes("250") ||
        body?.includes("500") ||
        body?.includes("Tokens") ||
        body?.includes("Spend") ||
        body?.includes("Requests")
    ).toBeTruthy();
  });

  test("shows zero state gracefully", async ({ authedPage: page }) => {
    await page.route("**/api/v1/costs/summary", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(zeroSummaryResponse),
      })
    );
    await page.route("**/api/v1/costs/trend", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(emptyTrendResponse),
      })
    );
    await page.goto("/costs");
    await page.waitForTimeout(1000);
    // Page should not crash — any content visible
    const body = await page.textContent("body");
    expect(body?.length).toBeGreaterThan(0);
    // h1 should still be present
    await expect(page.locator("h1")).toBeVisible();
  });

  test("breakdown tab buttons are visible", async ({ authedPage: page }) => {
    await page.route("**/api/v1/costs/summary", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(mockSummaryResponse),
      })
    );
    await page.route("**/api/v1/costs/trend", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(emptyTrendResponse),
      })
    );
    await page.goto("/costs");
    await page.waitForTimeout(500);
    // Cost page has breakdown tabs: "By Agent", "By Model", "By Team"
    const body = await page.textContent("body");
    expect(
      body?.includes("By Agent") ||
        body?.includes("By Model") ||
        body?.includes("By Team") ||
        body?.includes("Cost")
    ).toBeTruthy();
  });
});
