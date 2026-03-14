import { test, expect } from "./fixtures";

const MOCK_PR = {
  id: "pr-0001",
  title: "Update customer-support-agent prompts",
  resource_type: "agent",
  resource_name: "customer-support-agent",
  status: "submitted",
  submitter: "alice@test.com",
  reviewer: null,
  description: "Improved tone and accuracy",
  comments: [],
  created_at: "2026-03-10T00:00:00Z",
  updated_at: "2026-03-10T00:00:00Z",
};

const emptyPrsResponse = {
  data: { prs: [], total: 0, page: 1, per_page: 20 },
  meta: { page: 1, per_page: 20, total: 0 },
  errors: [],
};

const prsWithDataResponse = {
  data: { prs: [MOCK_PR], total: 1, page: 1, per_page: 20 },
  meta: { page: 1, per_page: 20, total: 1 },
  errors: [],
};

test.describe("Approvals Page", () => {
  test("renders approvals page with filters", async ({ authedPage: page }) => {
    await page.route("**/api/v1/git/prs", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(emptyPrsResponse),
      })
    );
    await page.goto("/approvals");
    await expect(page.locator("h1")).toContainText("Approvals");
    await expect(page.locator("select").first()).toBeVisible();
    await expect(page.locator("select").nth(1)).toBeVisible();
  });

  test("shows empty state when no PRs", async ({ authedPage: page }) => {
    await page.route("**/api/v1/git/prs", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(emptyPrsResponse),
      })
    );
    await page.goto("/approvals");
    await expect(page.getByText(/no pull requests found/i)).toBeVisible();
  });

  test("shows PR cards when PRs exist", async ({ authedPage: page }) => {
    await page.route("**/api/v1/git/prs", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(prsWithDataResponse),
      })
    );
    await page.goto("/approvals");
    await expect(
      page.getByText("Update customer-support-agent prompts")
    ).toBeVisible();
  });

  test("status filter options are correct", async ({ authedPage: page }) => {
    await page.route("**/api/v1/git/prs", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(emptyPrsResponse),
      })
    );
    await page.goto("/approvals");
    const statusSelect = page.locator("select").first();
    await expect(statusSelect).toBeVisible();
    const options = await statusSelect.locator("option").allTextContents();
    expect(options.some((o) => o.includes("All Statuses"))).toBeTruthy();
    expect(options.some((o) => o.includes("Submitted"))).toBeTruthy();
    expect(options.some((o) => o.includes("In Review"))).toBeTruthy();
    expect(options.some((o) => o.includes("Approved"))).toBeTruthy();
  });

  test("resource type filter options are correct", async ({ authedPage: page }) => {
    await page.route("**/api/v1/git/prs", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(emptyPrsResponse),
      })
    );
    await page.goto("/approvals");
    const typeSelect = page.locator("select").nth(1);
    await expect(typeSelect).toBeVisible();
    const options = await typeSelect.locator("option").allTextContents();
    expect(options.some((o) => o.includes("All Types"))).toBeTruthy();
    expect(options.some((o) => o.includes("Agent"))).toBeTruthy();
    expect(options.some((o) => o.includes("Prompt"))).toBeTruthy();
    expect(options.some((o) => o.includes("Tool"))).toBeTruthy();
  });

  test("changing status filter updates query", async ({ authedPage: page }) => {
    await page.route("**/api/v1/git/prs**", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(emptyPrsResponse),
      })
    );
    await page.goto("/approvals");
    const statusSelect = page.locator("select").first();
    await statusSelect.selectOption("submitted");
    await expect(statusSelect).toHaveValue("submitted");
  });

  test("shows pending review count in subtitle", async ({ authedPage: page }) => {
    await page.route("**/api/v1/git/prs", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(prsWithDataResponse),
      })
    );
    await page.goto("/approvals");
    await expect(page.getByText(/1 pending review/i)).toBeVisible();
  });

  test("PR card links to detail page", async ({ authedPage: page }) => {
    await page.route("**/api/v1/git/prs", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(prsWithDataResponse),
      })
    );
    await page.goto("/approvals");
    await expect(
      page.locator(`a[href="/approvals/${MOCK_PR.id}"]`)
    ).toBeVisible();
  });
});
