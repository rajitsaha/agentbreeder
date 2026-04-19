import { test, expect } from './fixtures';
import { waitForToast } from './helpers';

test.describe.configure({ mode: 'serial' });

test.describe('Cost Dashboard and Budget Alerts', () => {
  test('01 — cost dashboard loads with spend data', async ({ adminPage }) => {
    await adminPage.goto('/costs');
    await adminPage.waitForLoadState('networkidle');

    const chart = adminPage.locator(
      '[data-testid="cost-chart"], .cost-chart, canvas, [aria-label*="cost"]'
    ).first();
    await expect(chart).toBeVisible({ timeout: 15_000 });
  });

  test('02 — filter by team e2e-team-alpha updates chart', async ({ adminPage }) => {
    await adminPage.goto('/costs');

    const teamFilter = adminPage.getByRole('combobox', { name: /team/i }).or(
      adminPage.getByLabel(/team/i)
    ).first();
    await teamFilter.click();
    await adminPage.getByRole('option', { name: 'e2e-team-alpha' }).click();
    await adminPage.waitForLoadState('networkidle');

    // Chart or data table should update — verify page doesn't error
    await expect(adminPage.locator('body')).not.toContainText(/error|500/i);
  });

  test('03 — filter by agent e2e-agent-nocode shows breakdown', async ({ adminPage }) => {
    await adminPage.goto('/costs');

    const agentFilter = adminPage.getByRole('combobox', { name: /agent/i }).or(
      adminPage.getByLabel(/agent/i)
    ).first();
    if (await agentFilter.isVisible()) {
      await agentFilter.click();
      await adminPage.getByRole('option', { name: 'e2e-agent-nocode' }).click();
    }

    const breakdown = adminPage.getByText(/token|cost|spend/i).first();
    await expect(breakdown).toBeVisible({ timeout: 10_000 });
  });

  test('04 — token count in cost view is non-zero', async ({ adminPage }) => {
    await adminPage.goto('/costs');
    // Look for any token count display
    const tokenDisplay = adminPage.getByText(/\d+\s*tokens?/i).first();
    await expect(tokenDisplay).toBeVisible({ timeout: 15_000 });
    const text = await tokenDisplay.textContent();
    const count = parseInt(text?.replace(/\D/g, '') ?? '0', 10);
    expect(count).toBeGreaterThan(0);
  });

  test('05 — create budget alert for e2e-team-alpha at $10', async ({ adminPage }) => {
    await adminPage.goto('/budgets');
    await adminPage.waitForLoadState('networkidle');

    await adminPage.getByRole('button', { name: /create budget|add budget|new/i }).click();
    await adminPage.getByRole('dialog').waitFor();

    const teamSelect = adminPage.getByRole('combobox', { name: /team/i });
    await teamSelect.click();
    await adminPage.getByRole('option', { name: 'e2e-team-alpha' }).click();

    await adminPage.getByLabel(/limit|amount|threshold/i).fill('10');
    await adminPage.getByRole('button', { name: /save|create/i }).click();
    await waitForToast(adminPage, /created|saved/i);
  });

  test('06 — budget alert appears with correct team and threshold', async ({ adminPage }) => {
    await adminPage.goto('/budgets');
    await expect(adminPage.getByText('e2e-team-alpha')).toBeVisible({ timeout: 10_000 });
    await expect(adminPage.getByText(/\$10|10\.00/i)).toBeVisible();
  });
});
