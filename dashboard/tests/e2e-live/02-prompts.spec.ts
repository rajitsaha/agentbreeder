import { test, expect } from './fixtures';
import { waitForToast, navTo } from './helpers';

test.describe.configure({ mode: 'serial' });

test.describe('Prompt Lifecycle', () => {
  test('01 — create e2e-support-prompt via prompt builder', async ({ adminPage }) => {
    await adminPage.goto('/prompts');
    await adminPage.getByRole('button', { name: /new prompt|create/i }).click();
    await adminPage.waitForURL(/prompt-builder|prompts\/new/);

    await adminPage.getByLabel(/name/i).fill('e2e-support-prompt');
    const teamSelect = adminPage.getByRole('combobox', { name: /team/i });
    await teamSelect.click();
    await adminPage.getByRole('option', { name: 'e2e-team-alpha' }).click();

    const textarea = adminPage.getByLabel(/system prompt|system text/i).or(
      adminPage.getByRole('textbox', { name: /system/i })
    ).first();
    await textarea.fill('You are a helpful e2e support agent. Answer user questions clearly and concisely.');

    await adminPage.getByRole('button', { name: /save|create|register/i }).click();
    await waitForToast(adminPage, /saved|created|success/i);
  });

  test('02 — prompt appears in registry list', async ({ adminPage }) => {
    await navTo(adminPage, 'prompts');
    await expect(adminPage.getByText('e2e-support-prompt')).toBeVisible({ timeout: 10_000 });
  });

  test('03 — edit prompt and save as new version', async ({ adminPage }) => {
    await navTo(adminPage, 'prompts');
    await adminPage.getByText('e2e-support-prompt').click();
    await adminPage.waitForURL(/prompt-builder|prompts\//);

    const textarea = adminPage.getByLabel(/system prompt|system text/i).or(
      adminPage.getByRole('textbox', { name: /system/i })
    ).first();
    await textarea.fill('You are a helpful e2e support agent v2. Provide detailed answers.');

    await adminPage.getByRole('button', { name: /save as new version|save/i }).click();
    await waitForToast(adminPage, /saved|version|success/i);

    const versionSelector = adminPage.getByRole('combobox', { name: /version/i }).or(
      adminPage.locator('[data-testid="version-selector"]')
    );
    await expect(versionSelector).toBeVisible();
    await versionSelector.click();
    const options = adminPage.getByRole('option');
    await expect(options).toHaveCount(2);
  });

  test('04 — switch to v1 via version selector restores original text', async ({ adminPage }) => {
    await navTo(adminPage, 'prompts');
    await adminPage.getByText('e2e-support-prompt').click();

    const versionSelector = adminPage.getByRole('combobox', { name: /version/i }).or(
      adminPage.locator('[data-testid="version-selector"]')
    );
    await versionSelector.click();
    await adminPage.getByRole('option').first().click();

    const textarea = adminPage.getByLabel(/system prompt|system text/i).or(
      adminPage.getByRole('textbox', { name: /system/i })
    ).first();
    await expect(textarea).not.toContainText('v2');
  });

  test('05 — test prompt in test panel via LiteLLM fake', async ({ adminPage }) => {
    await navTo(adminPage, 'prompts');
    await adminPage.getByText('e2e-support-prompt').click();

    const testBtn = adminPage.getByRole('button', { name: /test|run|try/i }).first();
    await testBtn.click();

    const input = adminPage.getByPlaceholder(/user message|test input|message/i).or(
      adminPage.getByRole('textbox', { name: /input/i })
    ).first();
    await input.fill('Hello, what can you help me with?');
    await adminPage.getByRole('button', { name: /send|run test/i }).click();

    await expect(adminPage.locator('[data-testid="test-response"], .test-response, [role="region"]').last())
      .toBeVisible({ timeout: 30_000 });
  });

  test('06 — prompt appears in global search results', async ({ adminPage }) => {
    await adminPage.goto('/search?q=e2e-support');
    await expect(adminPage.getByText('e2e-support-prompt')).toBeVisible({ timeout: 10_000 });
  });

  test('07 — prompt is selectable in agent builder registry picker', async ({ adminPage }) => {
    await adminPage.goto('/agent-builder');
    await adminPage.waitForLoadState('networkidle');

    const addPromptBtn = adminPage.getByRole('button', { name: /add prompt|prompt/i }).first();
    await addPromptBtn.click();
    await adminPage.getByRole('dialog').waitFor();
    await expect(adminPage.getByText('e2e-support-prompt')).toBeVisible({ timeout: 10_000 });
    await adminPage.keyboard.press('Escape');
  });
});
