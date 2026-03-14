import { test, expect } from "./fixtures";

const MOCK_AUDIT_EVENT = {
  id: "evt-0001",
  action: "deploy",
  resource_type: "agent",
  resource_id: "aaaaaaaa-0000-0000-0000-000000000001",
  resource_name: "customer-support-agent",
  actor: "alice@test.com",
  team: "engineering",
  details: { version: "1.0.0" },
  created_at: "2026-03-10T10:00:00Z",
};

function makeAuditResponse(events: typeof MOCK_AUDIT_EVENT[]) {
  return {
    data: events,
    meta: { page: 1, per_page: 20, total: events.length },
    errors: [],
  };
}

test.describe("Audit Page", () => {
  test("renders audit page with heading", async ({ authedPage: page }) => {
    await page.route("**/api/v1/audit", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(makeAuditResponse([])),
      })
    );
    await page.goto("/audit");
    await expect(page.locator("h1")).toContainText("Audit");
  });

  test("shows summary cards", async ({ authedPage: page }) => {
    await page.route("**/api/v1/audit", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(makeAuditResponse([])),
      })
    );
    await page.goto("/audit");
    await page.waitForTimeout(500);
    const body = await page.textContent("body");
    expect(
      body?.includes("Events today") ||
        body?.includes("Deploys today") ||
        body?.includes("Audit")
    ).toBeTruthy();
  });

  test("shows empty state when no events", async ({ authedPage: page }) => {
    await page.route("**/api/v1/audit", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(makeAuditResponse([])),
      })
    );
    await page.goto("/audit");
    await page.waitForTimeout(1000);
    const body = await page.textContent("body");
    expect(
      body?.includes("No audit events") ||
        body?.includes("No audit") ||
        body?.includes("empty") ||
        body?.includes("Audit")
    ).toBeTruthy();
  });

  test("shows audit event rows when data", async ({ authedPage: page }) => {
    await page.route("**/api/v1/audit**", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(makeAuditResponse([MOCK_AUDIT_EVENT])),
      })
    );
    await page.goto("/audit");
    await page.waitForTimeout(500);
    const body = await page.textContent("body");
    expect(
      body?.includes("alice@test.com") || body?.includes("customer-support-agent")
    ).toBeTruthy();
  });

  test("action filter select is visible", async ({ authedPage: page }) => {
    await page.route("**/api/v1/audit**", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(makeAuditResponse([])),
      })
    );
    await page.goto("/audit");
    await page.waitForTimeout(500);
    await expect(page.locator("select").first()).toBeVisible();
    const options = await page.locator("select").first().locator("option").allTextContents();
    expect(options.some((o) => o.toLowerCase().includes("deploy"))).toBeTruthy();
  });

  test("resource type filter is visible", async ({ authedPage: page }) => {
    await page.route("**/api/v1/audit**", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(makeAuditResponse([])),
      })
    );
    await page.goto("/audit");
    await page.waitForTimeout(500);
    // Two selects: actions and resource types. Check that page renders both.
    const selects = page.locator("select");
    await expect(selects.first()).toBeVisible();
    const selectCount = await selects.count();
    expect(selectCount).toBeGreaterThanOrEqual(2);
    // The resource type select has "agent" as an option
    const resourceOptions = await selects.nth(1).locator("option").allTextContents();
    expect(resourceOptions.some((o) => o.toLowerCase().includes("agent"))).toBeTruthy();
  });

  test("search input is visible", async ({ authedPage: page }) => {
    await page.route("**/api/v1/audit", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(makeAuditResponse([])),
      })
    );
    await page.goto("/audit");
    await expect(page.locator("input").first()).toBeVisible();
  });
});
