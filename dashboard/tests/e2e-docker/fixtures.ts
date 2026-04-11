import { test as base, type Page } from "@playwright/test";
import { registerUser, loginUser, uniqueEmail } from "./helpers";

export interface RealAuthFixture {
  page: Page;
  token: string;
  email: string;
}

/**
 * Extended test fixture that registers a fresh user against the real API,
 * logs in to get a JWT, and seeds it into the browser's localStorage so
 * route guards pass without mocking.
 */
export const test = base.extend<{ authedPage: RealAuthFixture }>({
  authedPage: async ({ page }, use) => {
    const email = uniqueEmail();
    const password = "Test1234!";
    const name = "E2E Test User";
    const team = "engineering";

    // Register fresh user
    await registerUser({ email, password, name, team });

    // Login to get real JWT
    const { access_token } = await loginUser(email, password);

    // Inject token into browser storage before first navigation
    await page.goto("/login");
    await page.evaluate(
      (tok) => localStorage.setItem("ag-token", tok),
      access_token,
    );

    await use({ page, token: access_token, email });
  },
});

export { expect } from "@playwright/test";
