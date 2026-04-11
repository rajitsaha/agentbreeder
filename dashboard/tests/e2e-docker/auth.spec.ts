import { test, expect } from "@playwright/test";
import { uniqueEmail, registerUser } from "./helpers";

test.describe("Real auth flows", () => {
  test("user can register and land on dashboard", async ({ page }) => {
    const email = uniqueEmail("register");
    const password = "Test1234!";

    await page.goto("/login");

    // Switch to register mode — top-right button text is "Create an account"
    const switchBtn = page.getByRole("button", { name: /sign up|register|create\s+(?:an?\s+)?account/i });
    await switchBtn.click();

    // Fill registration form
    await page.locator('input[type="email"]').fill(email);
    await page.locator('input[type="password"]').fill(password);

    // Fill name/team if present (gracefully handle optional fields)
    const nameInput = page.locator('input[name="name"], input[placeholder*="name" i]').first();
    if (await nameInput.isVisible()) {
      await nameInput.fill("E2E User");
    }
    const teamInput = page.locator('input[name="team"], input[placeholder*="team" i]').first();
    if (await teamInput.isVisible()) {
      await teamInput.fill("engineering");
    }

    await page.locator('button[type="submit"]').click();

    // After successful registration, user should land on / or /agents
    await expect(page).toHaveURL(/\/(agents|$)/, { timeout: 10_000 });
  });

  test("user can login with valid credentials and see sidebar", async ({ page }) => {
    const email = uniqueEmail("login");
    const password = "Test1234!";

    // Pre-register via API (no UI needed for setup)
    await registerUser({ email, password, name: "Login Test User", team: "engineering" });

    await page.goto("/login");
    await page.locator('input[type="email"]').fill(email);
    await page.locator('input[type="password"]').fill(password);
    await page.locator('button[type="submit"]').click();

    // Should redirect to dashboard and show sidebar
    await expect(page).toHaveURL(/\/(agents|$)/, { timeout: 10_000 });
    await expect(page.locator("aside")).toBeVisible();
  });

  test("invalid login shows error message", async ({ page }) => {
    await page.goto("/login");
    await page.locator('input[type="email"]').fill("nobody@nowhere.invalid");
    await page.locator('input[type="password"]').fill("wrongpassword");
    await page.locator('button[type="submit"]').click();

    // Should stay on login page and show error
    await expect(page).toHaveURL(/\/login/, { timeout: 5_000 });
    const body = await page.textContent("body");
    expect(
      body?.toLowerCase().includes("invalid") ||
      body?.toLowerCase().includes("incorrect") ||
      body?.toLowerCase().includes("error") ||
      body?.toLowerCase().includes("failed"),
    ).toBe(true);
  });
});
