import { test, expect } from "./fixtures";

const emptyAgentsResponse = {
  data: [],
  meta: { page: 1, per_page: 20, total: 0 },
  errors: [],
};

const emptyAuditResponse = {
  data: [],
  meta: { page: 1, per_page: 500, total: 0 },
  errors: [],
};

const seededAuditResponse = {
  data: [
    {
      id: "evt-1",
      actor: "alice",
      actor_id: "u-1",
      action: "agent.created",
      resource_type: "agent",
      resource_id: "a-101",
      resource_name: "customer-support-v2",
      team: "engineering",
      details: {},
      ip_address: null,
      created_at: new Date(Date.now() - 30 * 60_000).toISOString(),
    },
    {
      id: "evt-2",
      actor: "bob",
      actor_id: "u-2",
      action: "tool.updated",
      resource_type: "tool",
      resource_id: "t-301",
      resource_name: "zendesk-mcp",
      team: "engineering",
      details: {},
      ip_address: null,
      created_at: new Date(Date.now() - 2 * 3600_000).toISOString(),
    },
  ],
  meta: { page: 1, per_page: 500, total: 2 },
  errors: [],
};

function mockAudit(page: import("@playwright/test").Page, body: object) {
  return page.route("**/api/v1/audit*", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(body),
    })
  );
}

test.describe("Activity Page", () => {
  test("renders activity page with heading", async ({ authedPage: page }) => {
    await page.route("**/api/v1/agents", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(emptyAgentsResponse),
      })
    );
    await mockAudit(page, emptyAuditResponse);
    await page.goto("/activity");
    await expect(page.locator("h1")).toContainText("Activity");
  });

  test("renders empty state when audit log is empty", async ({
    authedPage: page,
  }) => {
    await mockAudit(page, emptyAuditResponse);
    await page.goto("/activity");
    await expect(page.getByText(/no activity yet/i)).toBeVisible();
  });

  test("renders events from /api/v1/audit", async ({ authedPage: page }) => {
    await mockAudit(page, seededAuditResponse);
    await page.goto("/activity");
    // The adapter renders descriptions like "<actor> <action> <resource_type> <name>"
    await expect(page.getByText(/customer-support-v2/)).toBeVisible();
    await expect(page.getByText(/zendesk-mcp/)).toBeVisible();
  });

  test("page renders without crash", async ({ authedPage: page }) => {
    await mockAudit(page, emptyAuditResponse);
    await page.goto("/activity");
    await page.waitForTimeout(1000);
    const body = await page.textContent("body");
    expect(body?.length).toBeGreaterThan(0);
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
    await mockAudit(page, emptyAuditResponse);
    await page.goto("/activity");
    await page.waitForTimeout(500);
    const hasSelect = await page.locator("select").count();
    const hasFilterButton = await page
      .getByRole("button", { name: /all|agent|filter/i })
      .count();
    expect(hasSelect > 0 || hasFilterButton > 0).toBeTruthy();
  });
});
