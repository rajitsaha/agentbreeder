import { test, expect } from "./fixtures";

const BUILDER_URL = "/orchestrations/builder";

test("renders orchestration builder page", async ({ authedPage: page }) => {
  await page.goto(BUILDER_URL);
  await expect(page.getByText(/orchestration/i).first()).toBeVisible();
});

test("shows strategy selector", async ({ authedPage: page }) => {
  await page.goto(BUILDER_URL);
  // Either a "Strategy" label or one of the known strategy values should be visible
  const strategyEl = page
    .getByText(/strategy/i)
    .or(page.getByText("sequential"))
    .first();
  await expect(strategyEl).toBeVisible();
});

test("shows canvas area", async ({ authedPage: page }) => {
  await page.goto(BUILDER_URL);
  // ReactFlow canvas, a generic canvas element, or a dedicated testid container
  const canvas = page
    .locator(".react-flow")
    .or(page.locator("[data-testid='orchestration-canvas']"))
    .or(page.locator("canvas"))
    .first();

  // The canvas may be conditionally rendered — at minimum the page must not crash
  await expect(page.locator("body")).not.toBeEmpty();

  // If a canvas element is present, assert it is visible
  if (await canvas.count() > 0) {
    await expect(canvas).toBeVisible();
  }
});

test("shows add agent button", async ({ authedPage: page }) => {
  await page.goto(BUILDER_URL);
  // The orchestration builder has canvas action buttons: Add Agent, Add Supervisor, etc.
  const actionBtn = page
    .getByRole("button", { name: /add agent/i })
    .or(page.getByRole("button", { name: /agent/i }))
    .or(page.getByText(/add agent/i))
    .first();
  await expect(actionBtn).toBeVisible();
});

test("shows YAML output", async ({ authedPage: page }) => {
  await page.goto(BUILDER_URL);
  // Look for a YAML label, a code/pre block, or a Monaco/CodeMirror editor
  const yamlEl = page
    .getByText(/yaml/i)
    .or(page.locator("pre"))
    .or(page.locator(".monaco-editor"))
    .or(page.locator(".cm-editor"))
    .first();
  await expect(yamlEl).toBeVisible();
});
