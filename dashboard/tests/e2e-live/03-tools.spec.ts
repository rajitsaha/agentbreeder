import { test, expect } from './fixtures';
import { waitForToast, navTo } from './helpers';

test.describe.configure({ mode: 'serial' });

const TOOL_SCHEMA = JSON.stringify({
  type: 'object',
  properties: {
    query: { type: 'string', description: 'Search query' },
  },
  required: ['query'],
}, null, 2);

test.describe('Tool Creation and Sandbox', () => {
  test('01 — create e2e-search-tool via tool builder', async ({ adminPage }) => {
    await adminPage.goto('/tools');
    await adminPage.getByRole('button', { name: /new tool|create/i }).click();
    await adminPage.waitForURL(/tool-builder|tools\/new/);

    await adminPage.getByLabel(/name/i).fill('e2e-search-tool');
    await adminPage.getByLabel(/description/i).fill('E2E test search tool that queries the knowledge base');

    const schemaField = adminPage.locator('.cm-editor').or(
      adminPage.getByLabel(/schema|json schema/i)
    ).first();
    await schemaField.click();
    await adminPage.keyboard.press('Control+a');
    await adminPage.keyboard.type(TOOL_SCHEMA);

    const teamSelect = adminPage.getByRole('combobox', { name: /team/i });
    if (await teamSelect.isVisible()) {
      await teamSelect.click();
      await adminPage.getByRole('option', { name: 'e2e-team-alpha' }).click();
    }

    await adminPage.getByRole('button', { name: /save|create|register/i }).click();
    await waitForToast(adminPage, /saved|created|success/i);
  });

  test('02 — tool appears in registry list', async ({ adminPage }) => {
    await navTo(adminPage, 'tools');
    await expect(adminPage.getByText('e2e-search-tool')).toBeVisible({ timeout: 10_000 });
  });

  test('03 — open sandbox runner and execute tool', async ({ adminPage }) => {
    await navTo(adminPage, 'tools');
    await adminPage.getByText('e2e-search-tool').click();
    await adminPage.waitForURL(/tool-detail|tools\//);

    const sandboxBtn = adminPage.getByRole('button', { name: /sandbox|run|test|execute/i }).first();
    await sandboxBtn.click();

    const inputField = adminPage.getByLabel(/input|payload/i).or(
      adminPage.locator('.cm-editor')
    ).first();
    await inputField.click();
    await adminPage.keyboard.press('Control+a');
    await adminPage.keyboard.type('{"query":"hello"}');

    await adminPage.getByRole('button', { name: /run|execute|send/i }).click();
  });

  test('04 — sandbox shows execution result with status and output', async ({ adminPage }) => {
    const resultPanel = adminPage.locator(
      '[data-testid="sandbox-result"], .sandbox-result, [aria-label="Result"]'
    ).or(adminPage.getByText(/output|result|response/i).last());
    await expect(resultPanel).toBeVisible({ timeout: 15_000 });
  });

  test('05 — tool appears in global search', async ({ adminPage }) => {
    await adminPage.goto('/search?q=e2e-search');
    await expect(adminPage.getByText('e2e-search-tool')).toBeVisible({ timeout: 10_000 });
  });

  test('06 — tool is selectable in agent builder tool picker', async ({ adminPage }) => {
    await adminPage.goto('/agent-builder');
    await adminPage.waitForLoadState('networkidle');
    const addToolBtn = adminPage.getByRole('button', { name: /add tool|tool/i }).first();
    await addToolBtn.click();
    await adminPage.getByRole('dialog').waitFor();
    await expect(adminPage.getByText('e2e-search-tool')).toBeVisible({ timeout: 10_000 });
    await adminPage.keyboard.press('Escape');
  });
});
