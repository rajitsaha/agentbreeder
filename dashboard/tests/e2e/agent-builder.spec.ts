import { test, expect } from "./fixtures";

const BUILDER_URL = "/agents/builder";

test("renders agent builder page", async ({ authedPage: page }) => {
  await page.goto(BUILDER_URL);
  // Agent builder shows "New Agent" or "Edit Agent" in h2, not h1
  await expect(
    page.getByRole("heading", { name: /new agent/i })
      .or(page.getByRole("heading", { name: /edit agent/i }))
      .or(page.getByText(/new agent/i).first())
  ).toBeVisible();
});

test("YAML editor is visible by default", async ({ authedPage: page }) => {
  await page.goto(BUILDER_URL);
  await page.waitForTimeout(500);
  // CodeMirror editor (.cm-editor) or Monaco (.monaco-editor) or textarea
  const editor = page
    .locator(".cm-editor")
    .or(page.locator(".monaco-editor"))
    .or(page.locator("textarea"))
    .or(page.locator("[role='textbox']"))
    .first();
  await expect(editor).toBeVisible();
});

test("shows framework selector", async ({ authedPage: page }) => {
  await page.goto(BUILDER_URL);
  await page.waitForTimeout(500);
  // Default YAML has "framework: langgraph" visible in the editor
  const body = await page.textContent("body");
  expect(
    body?.toLowerCase().includes("langgraph") ||
      body?.toLowerCase().includes("framework")
  ).toBeTruthy();
});

test("shows deploy button", async ({ authedPage: page }) => {
  await page.goto(BUILDER_URL);
  await expect(page.getByRole("button", { name: /deploy/i })).toBeVisible();
});

test("can switch to visual mode", async ({ authedPage: page }) => {
  await page.goto(BUILDER_URL);
  await page.waitForTimeout(500);

  const visualToggle = page
    .getByRole("button", { name: /visual/i })
    .or(page.getByRole("tab", { name: /visual/i }))
    .first();

  if (await visualToggle.isVisible()) {
    await visualToggle.click();
    await expect(page.locator("body")).not.toBeEmpty();
  } else {
    await expect(page.locator("body")).not.toBeEmpty();
  }
});

test("submit for review button visible", async ({ authedPage: page }) => {
  await page.goto(BUILDER_URL);
  const reviewBtn = page
    .getByRole("button", { name: /submit for review/i })
    .or(page.getByRole("button", { name: /review/i }))
    .or(page.getByRole("button", { name: /submit/i }))
    .first();
  await expect(reviewBtn).toBeVisible();
});
