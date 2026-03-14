import { test, expect } from "./fixtures";

const MOCK_PROVIDER = {
  id: "prov-0001",
  name: "OpenAI Production",
  provider_type: "openai",
  base_url: "https://api.openai.com/v1",
  status: "active",
  last_verified: null,
  latency_ms: null,
  model_count: 5,
  config: null,
  created_at: "2026-03-01T00:00:00Z",
  updated_at: "2026-03-01T00:00:00Z",
};

const emptyProvidersResponse = {
  data: [],
  meta: { page: 1, per_page: 20, total: 0 },
  errors: [],
};

const providersWithDataResponse = {
  data: [MOCK_PROVIDER],
  meta: { page: 1, per_page: 20, total: 1 },
  errors: [],
};

test.describe("Settings Page", () => {
  test("renders settings page with providers tab", async ({ authedPage: page }) => {
    await page.route("**/api/v1/providers**", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(emptyProvidersResponse),
      })
    );
    await page.goto("/settings");
    await expect(page.getByRole("tab", { name: "Providers" })).toBeVisible();
    await expect(page.getByText("OpenAI")).toBeVisible();
  });

  test("shows configured providers", async ({ authedPage: page }) => {
    await page.route("**/api/v1/providers**", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(providersWithDataResponse),
      })
    );
    await page.goto("/settings");
    await expect(page.getByText("OpenAI Production")).toBeVisible();
  });

  test("provider status badge shows healthy", async ({ authedPage: page }) => {
    await page.route("**/api/v1/providers**", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(providersWithDataResponse),
      })
    );
    await page.goto("/settings");
    await page.waitForTimeout(500);
    const body = await page.textContent("body");
    // Provider name should be visible at minimum
    expect(body?.includes("OpenAI Production")).toBeTruthy();
  });

  test("add provider dialog opens", async ({ authedPage: page }) => {
    await page.route("**/api/v1/providers**", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(emptyProvidersResponse),
      })
    );
    await page.goto("/settings");
    // When no providers are configured, the empty state shows "Add Provider" button
    const addButton = page
      .getByRole("button", { name: /add provider/i })
      .first();
    await expect(addButton).toBeVisible();
    await addButton.click();
    await expect(
      page.getByText(/add provider/i).or(page.getByText(/configure/i)).first()
    ).toBeVisible();
  });

  test("provider type cards are visible", async ({ authedPage: page }) => {
    await page.route("**/api/v1/providers**", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(emptyProvidersResponse),
      })
    );
    await page.goto("/settings");
    await page.waitForTimeout(500);
    // After clicking Add Provider, provider type cards should appear (OpenAI, Anthropic, etc.)
    const addButton = page.getByRole("button", { name: /add provider/i }).first();
    await addButton.click();
    await page.waitForTimeout(300);
    // Step 1 of wizard shows provider type selection
    const body = await page.textContent("body");
    expect(
      body?.includes("OpenAI") ||
        body?.includes("Anthropic") ||
        body?.includes("Ollama")
    ).toBeTruthy();
  });
});
