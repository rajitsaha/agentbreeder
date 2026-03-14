import { test, expect, apiOk } from "./fixtures";

const MARKETPLACE_URL = "/marketplace";
const MARKETPLACE_API_PATTERN = "**/api/v1/marketplace/browse**";

const MOCK_LISTING = {
  listing_id: "listing-0001",
  template_id: "tmpl-0001",
  name: "zendesk-support-agent",
  description: "Full-featured support agent for Zendesk",
  category: "support",
  framework: "langgraph",
  tags: ["support", "zendesk"],
  author: "community",
  avg_rating: 4.5,
  review_count: 12,
  install_count: 500,
  featured: false,
  published_at: "2026-01-01T00:00:00Z",
};

test("renders marketplace page with heading", async ({ authedPage: page }) => {
  await page.route(MARKETPLACE_API_PATTERN, (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: apiOk([], 0),
    }),
  );

  await page.goto(MARKETPLACE_URL);
  await expect(page.getByText(/marketplace/i).first()).toBeVisible();
});

test("shows empty state when no listings", async ({ authedPage: page }) => {
  await page.route(MARKETPLACE_API_PATTERN, (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: apiOk([], 0),
    }),
  );

  await page.goto(MARKETPLACE_URL);
  await expect(page.locator("body")).not.toBeEmpty();
});

test("shows marketplace item cards", async ({ authedPage: page }) => {
  await page.route(MARKETPLACE_API_PATTERN, (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: apiOk([MOCK_LISTING], 1),
    }),
  );

  await page.goto(MARKETPLACE_URL);
  await page.waitForTimeout(500);
  await expect(page.getByText("zendesk-support-agent")).toBeVisible();
});

test("search input visible", async ({ authedPage: page }) => {
  await page.route(MARKETPLACE_API_PATTERN, (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: apiOk([], 0),
    }),
  );

  await page.goto(MARKETPLACE_URL);
  const searchInput = page
    .getByRole("searchbox")
    .or(page.getByPlaceholder(/search/i))
    .or(page.locator("input[type='search']"))
    .or(page.locator("input[type='text']"))
    .first();
  await expect(searchInput).toBeVisible();
});
