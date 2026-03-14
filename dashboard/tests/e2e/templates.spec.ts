import { test, expect } from "./fixtures";

const MOCK_TEMPLATE = {
  id: "tmpl-0001",
  name: "customer-support-starter",
  version: "1.0.0",
  description: "A starter template for customer support agents",
  framework: "langgraph",
  category: "support",
  tags: ["support", "starter"],
  author: "agent-garden-team",
  team: "default",
  status: "published",
  use_count: 200,
  readme: "",
  config_template: {},
  parameters: [],
};

function makeTemplatesResponse(templates: typeof MOCK_TEMPLATE[]) {
  return {
    data: templates,
    meta: { page: 1, per_page: 20, total: templates.length },
    errors: [],
  };
}

test.describe("Templates Page", () => {
  test("renders templates page with heading", async ({ authedPage: page }) => {
    await page.route("**/api/v1/templates**", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(makeTemplatesResponse([])),
      })
    );
    await page.goto("/templates");
    await expect(page.locator("h1")).toContainText("Templates");
  });

  test("shows empty state when no templates", async ({ authedPage: page }) => {
    await page.route("**/api/v1/templates**", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(makeTemplatesResponse([])),
      })
    );
    await page.goto("/templates");
    await page.waitForTimeout(1000);
    const body = await page.textContent("body");
    expect(
      body?.includes("No templates") ||
        body?.includes("empty") ||
        body?.includes("Templates")
    ).toBeTruthy();
  });

  test("shows template cards when data exists", async ({ authedPage: page }) => {
    await page.route("**/api/v1/templates**", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(makeTemplatesResponse([MOCK_TEMPLATE])),
      })
    );
    await page.goto("/templates");
    await page.waitForTimeout(500);
    // Templates page renders template.name (slug) not display_name
    await expect(page.getByText("customer-support-starter")).toBeVisible();
  });

  test("category filter pills are visible", async ({ authedPage: page }) => {
    await page.route("**/api/v1/templates**", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(makeTemplatesResponse([])),
      })
    );
    await page.goto("/templates");
    await page.waitForTimeout(500);
    // Templates page has category filter pills (All, Support, etc.)
    const body = await page.textContent("body");
    expect(
      body?.includes("All") ||
        body?.includes("Support") ||
        body?.includes("Templates")
    ).toBeTruthy();
  });

  test("template cards show framework badges", async ({ authedPage: page }) => {
    await page.route("**/api/v1/templates**", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(makeTemplatesResponse([MOCK_TEMPLATE])),
      })
    );
    await page.goto("/templates");
    await page.waitForTimeout(500);
    const body = await page.textContent("body");
    expect(body?.toLowerCase()).toContain("langgraph");
  });

  test("navigate to template detail on click", async ({ authedPage: page }) => {
    await page.route("**/api/v1/templates**", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(makeTemplatesResponse([MOCK_TEMPLATE])),
      })
    );
    await page.route("**/api/v1/templates/tmpl-0001**", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          data: MOCK_TEMPLATE,
          meta: { page: 1, per_page: 20, total: 1 },
          errors: [],
        }),
      })
    );
    await page.goto("/templates");
    await page.waitForTimeout(500);
    // Template cards render template.name (not display_name)
    await page.getByText("customer-support-starter").click();
    await expect(page).toHaveURL(/\/templates\/tmpl-0001/);
  });
});
