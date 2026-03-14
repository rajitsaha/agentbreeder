import { test, expect, MOCK_AGENT, apiOk } from "./fixtures";

const AGENT_ID = "aaaaaaaa-0000-0000-0000-000000000001";
const AGENT_DETAIL_URL = `/agents/${AGENT_ID}`;
const AGENT_API_PATTERN = `**/api/v1/agents/${AGENT_ID}`;
const AGENTS_LIST_API_PATTERN = "**/api/v1/agents";

function mockAgentDetail(page: Parameters<typeof test>[1] extends (args: { authedPage: infer P }) => unknown ? P : never) {
  return page.route(AGENT_API_PATTERN, (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: apiOk(MOCK_AGENT, 1),
    }),
  );
}

test("renders agent detail page", async ({ authedPage: page }) => {
  await page.route(AGENT_API_PATTERN, (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: apiOk(MOCK_AGENT, 1),
    }),
  );

  await page.goto(AGENT_DETAIL_URL);
  await expect(page.getByText("customer-support-agent")).toBeVisible();
});

test("shows agent framework and model", async ({ authedPage: page }) => {
  await page.route(AGENT_API_PATTERN, (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: apiOk(MOCK_AGENT, 1),
    }),
  );

  await page.goto(AGENT_DETAIL_URL);
  await expect(page.getByText("langgraph").first()).toBeVisible();
  await expect(page.getByText("claude-sonnet-4").first()).toBeVisible();
});

test("shows status badge", async ({ authedPage: page }) => {
  await page.route(AGENT_API_PATTERN, (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: apiOk(MOCK_AGENT, 1),
    }),
  );

  await page.goto(AGENT_DETAIL_URL);
  await expect(page.getByText("running")).toBeVisible();
});

test("shows team and owner info", async ({ authedPage: page }) => {
  await page.route(AGENT_API_PATTERN, (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: apiOk(MOCK_AGENT, 1),
    }),
  );

  await page.goto(AGENT_DETAIL_URL);
  await expect(page.getByText("engineering")).toBeVisible();
});

test("back navigation works", async ({ authedPage: page }) => {
  await page.route(AGENT_API_PATTERN, (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: apiOk(MOCK_AGENT, 1),
    }),
  );
  await page.route(AGENTS_LIST_API_PATTERN, (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: apiOk([MOCK_AGENT], 1),
    }),
  );

  await page.goto(AGENT_DETAIL_URL);

  // Click back button or breadcrumb containing "Agents"
  const backLink = page.getByRole("link", { name: /agents/i }).first();
  await backLink.click();

  await expect(page).toHaveURL("/agents");
});

test("shows loading state", async ({ authedPage: page }) => {
  // No mock — let the request hang so we can observe loading UI,
  // or observe that the page at least renders without a hard crash.
  await page.goto(AGENT_DETAIL_URL);

  // The page should render something quickly (loading skeleton, spinner, or
  // an error/empty state) — it must not be a blank white page.
  await expect(page.locator("body")).not.toBeEmpty();
});
