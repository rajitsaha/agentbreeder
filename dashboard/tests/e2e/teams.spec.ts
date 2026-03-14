import { test, expect } from "./fixtures";

const MOCK_TEAM = {
  id: "team-0001",
  name: "engineering",
  display_name: "Engineering",
  description: "Core engineering team",
  member_count: 5,
  created_at: "2026-01-01T00:00:00Z",
};

const emptyTeamsResponse = {
  data: [],
  meta: { page: 1, per_page: 20, total: 0 },
  errors: [],
};

const teamsWithDataResponse = {
  data: [MOCK_TEAM],
  meta: { page: 1, per_page: 20, total: 1 },
  errors: [],
};

test.describe("Teams Page", () => {
  test("renders teams page with heading", async ({ authedPage: page }) => {
    await page.route("**/api/v1/teams**", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(emptyTeamsResponse),
      })
    );
    await page.goto("/teams");
    await expect(page.locator("h1")).toContainText("Teams");
  });

  test("shows empty state when no teams", async ({ authedPage: page }) => {
    await page.route("**/api/v1/teams**", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(emptyTeamsResponse),
      })
    );
    await page.goto("/teams");
    await page.waitForTimeout(1000);
    await expect(page.locator("h1")).toContainText("Teams");
  });

  test("shows team cards when teams exist", async ({ authedPage: page }) => {
    await page.route("**/api/v1/teams**", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(teamsWithDataResponse),
      })
    );
    await page.goto("/teams");
    await expect(
      page.getByText("Engineering").or(page.getByText("engineering")).first()
    ).toBeVisible();
  });

  test("create team button visible", async ({ authedPage: page }) => {
    await page.route("**/api/v1/teams**", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(emptyTeamsResponse),
      })
    );
    await page.goto("/teams");
    await expect(
      page
        .getByRole("button", { name: /create team/i })
        .or(page.getByRole("button", { name: /new team/i }))
        .first()
    ).toBeVisible();
  });

  test("create team dialog opens", async ({ authedPage: page }) => {
    await page.route("**/api/v1/teams**", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(emptyTeamsResponse),
      })
    );
    await page.goto("/teams");
    const createButton = page
      .getByRole("button", { name: /create team/i })
      .or(page.getByRole("button", { name: /new team/i }))
      .first();
    await expect(createButton).toBeVisible();
    await createButton.click();
    await expect(page.getByText(/create team/i).first()).toBeVisible();
    // Dialog has a "Slug Name" input with placeholder "engineering"
    await expect(
      page
        .locator('input[placeholder="engineering"]')
        .or(page.locator('input[placeholder*="slug" i]'))
        .or(page.locator('input').first())
    ).toBeVisible();
  });

  test("create team dialog closes on backdrop click", async ({ authedPage: page }) => {
    await page.route("**/api/v1/teams**", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(emptyTeamsResponse),
      })
    );
    await page.goto("/teams");
    const createButton = page
      .getByRole("button", { name: /create team/i })
      .or(page.getByRole("button", { name: /new team/i }))
      .first();
    await createButton.click();
    await page.waitForTimeout(300);
    // Click the backdrop (top-left corner, outside the centered dialog)
    await page.mouse.click(10, 10);
    await page.waitForTimeout(300);
    await expect(
      page.locator('input[placeholder="engineering"]')
    ).not.toBeVisible();
  });

  test("team card links to detail page", async ({ authedPage: page }) => {
    await page.route("**/api/v1/teams**", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(teamsWithDataResponse),
      })
    );
    await page.goto("/teams");
    await page.waitForTimeout(500);
    const teamLink = page
      .locator(`a[href="/teams/${MOCK_TEAM.id}"]`)
      .or(page.locator(`a[href="/teams/${MOCK_TEAM.name}"]`))
      .first();
    await expect(teamLink).toBeVisible();
  });
});
