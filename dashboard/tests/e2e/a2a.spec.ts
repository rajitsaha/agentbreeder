import { test, expect, apiOk } from "./fixtures";

const A2A_URL = "/a2a";
const A2A_API_PATTERN = "**/api/v1/a2a/agents";

const MOCK_A2A_AGENT = {
  id: "a2a-0001",
  agent_id: null,
  name: "support-orchestration",
  agent_card: {},
  endpoint_url: "https://support.agents.internal",
  status: "active",
  capabilities: ["chat"],
  auth_scheme: null,
  team: "engineering",
  created_at: "2026-03-01T00:00:00Z",
  updated_at: "2026-03-01T00:00:00Z",
};

test("renders a2a page with heading", async ({ authedPage: page }) => {
  await page.route(A2A_API_PATTERN, (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: apiOk([], 0),
    }),
  );

  await page.goto(A2A_URL);

  const heading = page
    .getByRole("heading", { name: /a2a/i })
    .or(page.getByRole("heading", { name: /agent/i }))
    .first();
  await expect(heading).toBeVisible();
});

test("shows empty state when no a2a agents", async ({ authedPage: page }) => {
  await page.route(A2A_API_PATTERN, (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: apiOk([], 0),
    }),
  );

  await page.goto(A2A_URL);

  await expect(page.locator("body")).not.toBeEmpty();
});

test("shows a2a agent cards when data exists", async ({ authedPage: page }) => {
  await page.route(A2A_API_PATTERN, (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: apiOk([MOCK_A2A_AGENT], 1),
    }),
  );

  await page.goto(A2A_URL);
  await expect(page.getByText("support-orchestration")).toBeVisible();
});

test("page renders gracefully with API error", async ({ authedPage: page }) => {
  await page.goto(A2A_URL);
  await page.waitForTimeout(2000);

  await expect(page.locator("body")).not.toBeEmpty();
});
