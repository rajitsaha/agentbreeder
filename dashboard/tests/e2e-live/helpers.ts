import type { Page } from '@playwright/test';
import { expect } from '@playwright/test';

/** Waits for a toast/notification containing `text` to appear within 8 seconds. */
export async function waitForToast(page: Page, text: string | RegExp): Promise<void> {
  const toast = page
    .locator('[role="status"], [data-sonner-toast], .toast, [data-toast]')
    .filter({ hasText: text });
  await expect(toast).toBeVisible({ timeout: 8_000 });
}

/** Fills a CodeMirror editor with the given text (select-all then type). */
export async function fillYamlEditor(page: Page, yaml: string): Promise<void> {
  const editor = page.locator('.cm-editor, .cm-content, [data-language="yaml"]').first();
  await editor.click();
  await page.keyboard.press('Control+a');
  await page.keyboard.press('Delete');
  await page.keyboard.type(yaml, { delay: 0 });
}

/** Navigates to /playground and selects the named agent from the selector. */
export async function openSandbox(page: Page, agentName: string): Promise<void> {
  await page.goto('/playground');
  await page.waitForLoadState('networkidle');
  const selector = page.getByRole('combobox').or(page.locator('[data-testid="agent-selector"]')).first();
  await expect(selector).toBeVisible({ timeout: 5_000 });
  await selector.click();
  await page.getByRole('option', { name: agentName }).click();
}

/** Polls a condition until true or timeout (ms). */
export async function pollUntil(
  fn: () => Promise<boolean>,
  timeoutMs = 30_000,
  intervalMs = 2_000,
): Promise<void> {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    if (await fn()) return;
    const remaining = deadline - Date.now();
    if (remaining > 0) {
      await new Promise((r) => setTimeout(r, Math.min(intervalMs, remaining)));
    }
  }
  throw new Error(`pollUntil timed out after ${timeoutMs}ms`);
}

/** Clicks a sidebar nav link by its label text. */
export async function navTo(page: Page, label: string): Promise<void> {
  await page.getByRole('navigation').getByRole('link', { name: new RegExp(label, 'i') }).click();
  await page.waitForLoadState('networkidle');
}

/** Opens the registry picker dialog and selects an item by name. */
export async function pickFromRegistry(page: Page, buttonLabel: string, itemName: string): Promise<void> {
  await page.getByRole('button', { name: new RegExp(buttonLabel, 'i') }).click();
  await page.waitForSelector('[role="dialog"]');
  await page.getByRole('searchbox').fill(itemName);
  await page.getByRole('option', { name: itemName }).or(
    page.getByText(itemName).nth(0)
  ).click();
}
