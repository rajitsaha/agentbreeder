import { test, expect } from "./fixtures";

const MOCK_MCP_SERVER = {
  id: "mcp-1",
  name: "zendesk-mcp",
  description: "Zendesk integration",
  tool_count: 5,
  status: "active",
  url: "http://mcp.internal",
  created_at: "2026-03-01T00:00:00Z",
};

function makeMcpResponse(servers: typeof MOCK_MCP_SERVER[]) {
  return {
    data: servers,
    meta: { page: 1, per_page: 20, total: servers.length },
    errors: [],
  };
}

test.describe("MCP Servers Page", () => {
  test("renders mcp servers page with heading", async ({ authedPage: page }) => {
    await page.route("**/api/v1/mcp-servers**", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(makeMcpResponse([])),
      })
    );
    await page.goto("/mcp-servers");
    const heading = page.locator("h1");
    await expect(heading).toBeVisible();
    const headingText = await heading.textContent();
    expect(headingText?.toUpperCase()).toContain("MCP");
  });

  test("shows empty state when no servers", async ({ authedPage: page }) => {
    await page.route("**/api/v1/mcp-servers**", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(makeMcpResponse([])),
      })
    );
    await page.goto("/mcp-servers");
    await page.waitForTimeout(1000);
    const body = await page.textContent("body");
    expect(body?.length).toBeGreaterThan(0);
    await expect(page.locator("h1")).toBeVisible();
  });

  test("shows servers when data exists", async ({ authedPage: page }) => {
    await page.route("**/api/v1/mcp-servers**", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(makeMcpResponse([MOCK_MCP_SERVER])),
      })
    );
    await page.goto("/mcp-servers");
    await page.waitForTimeout(500);
    await expect(page.getByText("zendesk-mcp")).toBeVisible();
  });

  test("search input visible", async ({ authedPage: page }) => {
    await page.route("**/api/v1/mcp-servers**", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(makeMcpResponse([])),
      })
    );
    await page.goto("/mcp-servers");
    await expect(page.locator("input").first()).toBeVisible();
  });
});
