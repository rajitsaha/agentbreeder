import { test, expect } from "@playwright/test";

test.describe("Authentication", () => {
  test.beforeEach(async ({ page }) => {
    // Clear auth state before each test
    await page.goto("/login");
    await page.evaluate(() => localStorage.removeItem("ag-token"));
  });

  test("login page renders with form", async ({ page }) => {
    await page.goto("/login");
    await expect(page.locator("h2")).toContainText("Welcome back");
    await expect(page.locator('input[type="email"]')).toBeVisible();
    await expect(page.locator('input[type="password"]')).toBeVisible();
    await expect(page.locator('button[type="submit"]')).toContainText("Sign in");
  });

  test("can toggle between login and register modes", async ({ page }) => {
    await page.goto("/login");
    // Initially in login mode
    await expect(page.locator("h2")).toContainText("Welcome back");
    await expect(page.locator("#name")).not.toBeVisible();

    // Switch to register
    await page.getByText("Create an account").click();
    await expect(page.locator("h2")).toContainText("Create your account");
    await expect(page.locator("#name")).toBeVisible();
    await expect(page.locator("#team")).toBeVisible();
    await expect(page.locator('button[type="submit"]')).toContainText("Create account");

    // Switch back to login
    await page.getByText("Already have an account?").click();
    await expect(page.locator("h2")).toContainText("Welcome back");
  });

  test("shows error on invalid login", async ({ page }) => {
    await page.goto("/login");

    // Mock API to return 401
    await page.route("**/api/v1/auth/login", (route) =>
      route.fulfill({
        status: 401,
        contentType: "application/json",
        body: JSON.stringify({ detail: "Invalid email or password" }),
      }),
    );

    await page.fill('input[type="email"]', "bad@test.com");
    await page.fill('input[type="password"]', "wrongpass");
    await page.click('button[type="submit"]');

    await expect(page.getByText("Invalid email or password")).toBeVisible();
  });

  test("successful login redirects to home", async ({ page }) => {
    await page.goto("/login");

    // Mock login API
    await page.route("**/api/v1/auth/login", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          data: { access_token: "test-jwt-token", token_type: "bearer" },
          meta: { page: 1, per_page: 20, total: 0 },
          errors: [],
        }),
      }),
    );

    // Mock /me API
    await page.route("**/api/v1/auth/me", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          data: {
            id: "11111111-1111-1111-1111-111111111111",
            email: "user@test.com",
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

    // Mock the agents/tools APIs so home page doesn't error
    await page.route("**/api/v1/agents*", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ data: [], meta: { page: 1, per_page: 20, total: 0 }, errors: [] }),
      }),
    );
    await page.route("**/api/v1/registry/tools*", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ data: [], meta: { page: 1, per_page: 20, total: 0 }, errors: [] }),
      }),
    );

    await page.fill('input[type="email"]', "user@test.com");
    await page.fill('input[type="password"]', "password123");
    await page.click('button[type="submit"]');

    // Should redirect to home
    await page.waitForURL("/");
    await expect(page.locator("h1")).toContainText("Overview");
  });

  test("unauthenticated users are redirected to login", async ({ page }) => {
    // Mock /me to return 401 (no valid token)
    await page.route("**/api/v1/auth/me", (route) =>
      route.fulfill({ status: 401, contentType: "application/json", body: JSON.stringify({ detail: "Not authenticated" }) }),
    );

    await page.goto("/agents");
    await page.waitForURL("/login");
    await expect(page.locator("h2")).toContainText("Welcome back");
  });

  test("password visibility toggle works", async ({ page }) => {
    await page.goto("/login");
    const passwordInput = page.locator("#password");
    await expect(passwordInput).toHaveAttribute("type", "password");

    // Click eye icon to show password
    await page.locator("#password ~ button").click();
    await expect(passwordInput).toHaveAttribute("type", "text");

    // Click again to hide
    await page.locator("#password ~ button").click();
    await expect(passwordInput).toHaveAttribute("type", "password");
  });

  test("register mode shows validation for short password", async ({ page }) => {
    await page.goto("/login");
    await page.getByText("Create an account").click();

    // Mock API to return 422
    await page.route("**/api/v1/auth/register", (route) =>
      route.fulfill({
        status: 422,
        contentType: "application/json",
        body: JSON.stringify({ detail: "Password must be at least 8 characters" }),
      }),
    );

    await page.fill("#name", "Test");
    await page.fill('input[type="email"]', "new@test.com");
    await page.fill('input[type="password"]', "short");
    // Force submit despite HTML validation
    await page.evaluate(() => {
      const form = document.querySelector("form");
      form?.setAttribute("novalidate", "true");
    });
    await page.click('button[type="submit"]');

    await expect(page.getByText("Password must be at least 8 characters")).toBeVisible();
  });

  test("branding panel is visible on large screens", async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 720 });
    await page.goto("/login");
    await expect(page.getByText("Define Once.")).toBeVisible();
    await expect(page.getByText("Deploy Anywhere.")).toBeVisible();
  });

  test("logout clears session and redirects to login", async ({ page }) => {
    // Set up authenticated state
    await page.goto("/login");

    // Mock all required APIs
    await page.route("**/api/v1/auth/me", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          data: {
            id: "11111111-1111-1111-1111-111111111111",
            email: "user@test.com",
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
    await page.route("**/api/v1/agents*", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ data: [], meta: { page: 1, per_page: 20, total: 0 }, errors: [] }),
      }),
    );
    await page.route("**/api/v1/registry/tools*", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ data: [], meta: { page: 1, per_page: 20, total: 0 }, errors: [] }),
      }),
    );

    // Set token in localStorage to simulate logged-in state
    await page.evaluate(() => localStorage.setItem("ag-token", "fake-token"));
    await page.goto("/");
    await page.waitForURL("/");

    // User menu should show initials
    await expect(page.getByText("TU")).toBeVisible();
    await expect(page.getByText("Test User")).toBeVisible();

    // Click logout
    await page.locator('button[title="Sign out"]').click();

    // Should redirect to login — need to handle that /me now returns 401
    await page.unroute("**/api/v1/auth/me");
    await page.route("**/api/v1/auth/me", (route) =>
      route.fulfill({ status: 401, contentType: "application/json", body: JSON.stringify({ detail: "Not authenticated" }) }),
    );

    await page.waitForURL("/login");
  });
});
