import { test, expect } from "./fixtures";

const MOCK_TRACE = {
  trace_id: "trace-0001",
  agent_id: "aaaaaaaa-0000-0000-0000-000000000001",
  agent_name: "customer-support-agent",
  status: "success",
  duration_ms: 1234,
  token_count: 542,
  cost_usd: 0.0023,
  model: "claude-sonnet-4",
  started_at: "2026-03-10T10:00:00Z",
  ended_at: "2026-03-10T10:00:01Z",
  span_count: 5,
  error_message: null,
};

const emptyTracesResponse = {
  data: [],
  meta: { page: 1, per_page: 20, total: 0 },
  errors: [],
};

const tracesWithDataResponse = {
  data: [MOCK_TRACE],
  meta: { page: 1, per_page: 20, total: 1 },
  errors: [],
};

test.describe("Traces Page", () => {
  test("renders traces page with heading and search", async ({ authedPage: page }) => {
    await page.route("**/api/v1/traces**", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(emptyTracesResponse),
      })
    );
    await page.goto("/traces");
    await expect(page.locator("h1")).toContainText("Traces");
    await expect(page.locator('input[placeholder*="search" i], input[placeholder*="Search" i]')).toBeVisible();
  });

  test("shows empty state when no traces", async ({ authedPage: page }) => {
    await page.route("**/api/v1/traces**", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(emptyTracesResponse),
      })
    );
    await page.goto("/traces");
    await page.waitForTimeout(1000);
    const rows = page.locator("tbody tr");
    const rowCount = await rows.count();
    expect(rowCount).toBe(0);
  });

  test("shows trace rows when data exists", async ({ authedPage: page }) => {
    await page.route("**/api/v1/traces**", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(tracesWithDataResponse),
      })
    );
    await page.goto("/traces");
    await page.waitForTimeout(500);
    // Look for agent name in the trace row link (not in the filter dropdown option)
    await expect(page.locator("a").filter({ hasText: "customer-support-agent" }).first()).toBeVisible();
  });

  test("status filter is visible", async ({ authedPage: page }) => {
    await page.route("**/api/v1/traces**", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(emptyTracesResponse),
      })
    );
    await page.goto("/traces");
    const statusSelect = page.locator("select").first();
    await expect(statusSelect).toBeVisible();
    const options = await statusSelect.locator("option").allTextContents();
    expect(
      options.some(
        (o) =>
          o.toLowerCase().includes("all") ||
          o.toLowerCase().includes("success") ||
          o.toLowerCase().includes("status")
      )
    ).toBeTruthy();
  });

  test("search input updates value", async ({ authedPage: page }) => {
    await page.route("**/api/v1/traces**", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(emptyTracesResponse),
      })
    );
    await page.goto("/traces");
    const searchInput = page.locator(
      'input[placeholder*="search" i], input[placeholder*="Search" i]'
    );
    await expect(searchInput).toBeVisible();
    await searchInput.fill("support");
    await expect(searchInput).toHaveValue("support");
  });
});
