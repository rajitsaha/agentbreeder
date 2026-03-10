import { test as base, type Page } from "@playwright/test";

/** Seed localStorage with a fake token and mock /me endpoint so route guards pass. */
async function setupAuth(page: Page) {
  // Mock /me to return a valid user
  await page.route("**/api/v1/auth/me", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        data: {
          id: "11111111-1111-1111-1111-111111111111",
          email: "test@test.com",
          name: "Test User",
          role: "viewer",
          team: "engineering",
          is_active: true,
          created_at: "2026-03-09T00:00:00Z",
        },
        meta: { page: 1, per_page: 20, total: 0 },
        errors: [],
      }),
    }),
  );

  // Set token before navigating
  await page.goto("/login");
  await page.evaluate(() => localStorage.setItem("ag-token", "test-token"));
}

/** Extended test fixture that pre-authenticates every test. */
export const test = base.extend<{ authedPage: Page }>({
  authedPage: async ({ page }, use) => {
    await setupAuth(page);
    await use(page);
  },
});

export { expect } from "@playwright/test";
