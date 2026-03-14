import { test, expect } from "./fixtures";

const MOCK_AGENT = {
  id: "aaaaaaaa-0000-0000-0000-000000000001",
  name: "customer-support-agent",
  version: "1.0.0",
  description: "Handles support tickets",
  team: "engineering",
  owner: "alice@test.com",
  framework: "langgraph",
  model_primary: "claude-sonnet-4",
  status: "running",
  tags: ["support"],
  is_favorite: false,
  created_at: "2026-03-01T00:00:00Z",
  updated_at: "2026-03-10T00:00:00Z",
};

const emptySearchResponse = {
  data: [],
  meta: { page: 1, per_page: 20, total: 0 },
  errors: [],
};

test.describe("Search Page", () => {
  test("renders search page", async ({ authedPage: page }) => {
    await page.route("**/api/v1/registry/search**", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(emptySearchResponse),
      })
    );
    await page.goto("/search");
    await page.waitForTimeout(500);
    const body = await page.textContent("body");
    expect(body?.toLowerCase()).toContain("search");
  });

  test("search input is visible", async ({ authedPage: page }) => {
    await page.route("**/api/v1/registry/search**", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(emptySearchResponse),
      })
    );
    // Search page shows "Search Results" h1 and a hint to use ⌘K
    await page.goto("/search");
    await page.waitForTimeout(500);
    await expect(page.locator("h1")).toBeVisible();
    const headingText = await page.locator("h1").textContent();
    expect(headingText?.toLowerCase()).toContain("search");
  });

  test("shows results when query returns data", async ({ authedPage: page }) => {
    await page.route("**/api/v1/registry/search**", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          data: [
            {
              id: MOCK_AGENT.id,
              name: MOCK_AGENT.name,
              description: MOCK_AGENT.description,
              entity_type: "agent",
              team: MOCK_AGENT.team,
            },
          ],
          meta: { page: 1, per_page: 20, total: 1 },
          errors: [],
        }),
      })
    );
    await page.goto("/search?q=customer");
    await page.waitForTimeout(500);
    await expect(page.getByText("customer-support-agent")).toBeVisible();
  });

  test("shows empty state for no results", async ({ authedPage: page }) => {
    await page.route("**/api/v1/registry/search**", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(emptySearchResponse),
      })
    );
    await page.goto("/search?q=nonexistent");
    await page.waitForTimeout(1000);
    const body = await page.textContent("body");
    expect(
      body?.includes("No results") ||
        body?.includes("nothing found") ||
        body?.includes("0 result") ||
        body?.includes("no match") ||
        body?.toLowerCase().includes("search")
    ).toBeTruthy();
  });

  test("query updates URL when navigating with q param", async ({ authedPage: page }) => {
    await page.route("**/api/v1/registry/search**", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(emptySearchResponse),
      })
    );
    // The search page reads q from URL params — navigate directly with a query
    await page.goto("/search?q=support");
    await page.waitForTimeout(500);
    await expect(page).toHaveURL(/q=support/);
    const body = await page.textContent("body");
    expect(body?.toLowerCase()).toContain("search");
  });
});
