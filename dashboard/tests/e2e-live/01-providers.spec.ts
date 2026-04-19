import { test, expect } from './fixtures';
import { waitForToast, navTo } from './helpers';

test.describe.configure({ mode: 'serial' });

test.describe('Provider Registration', () => {
  test.beforeEach(async ({ adminPage }) => {
    await adminPage.goto('/settings');
    await adminPage.waitForLoadState('networkidle');
  });

  test('01 — register OpenAI provider', async ({ adminPage }) => {
    await adminPage.getByRole('button', { name: /add provider/i }).click();
    await adminPage.getByRole('dialog').waitFor();
    await adminPage.getByLabel(/name/i).fill('e2e-openai');
    await adminPage.getByRole('combobox', { name: /type|provider type/i }).selectOption('openai');
    await adminPage.getByLabel(/api key/i).fill('sk-e2e-fake-openai-key');
    await adminPage.getByRole('button', { name: /save|create/i }).click();
    await waitForToast(adminPage, /saved|created|success/i);
  });

  test('02 — OpenAI appears in model catalog', async ({ adminPage }) => {
    await navTo(adminPage, 'models');
    await expect(adminPage.getByText(/openai/i).first()).toBeVisible();
  });

  test('03 — register Anthropic provider', async ({ adminPage }) => {
    await adminPage.goto('/settings');
    await adminPage.getByRole('button', { name: /add provider/i }).click();
    await adminPage.getByRole('dialog').waitFor();
    await adminPage.getByLabel(/name/i).fill('e2e-anthropic');
    await adminPage.getByRole('combobox', { name: /type|provider type/i }).selectOption('anthropic');
    await adminPage.getByLabel(/api key/i).fill('sk-ant-e2e-fake-key');
    await adminPage.getByRole('button', { name: /save|create/i }).click();
    await waitForToast(adminPage, /saved|created|success/i);
  });

  test('04 — register Google Gemini provider', async ({ adminPage }) => {
    await adminPage.goto('/settings');
    await adminPage.getByRole('button', { name: /add provider/i }).click();
    await adminPage.getByRole('dialog').waitFor();
    await adminPage.getByLabel(/name/i).fill('e2e-gemini');
    await adminPage.getByRole('combobox', { name: /type|provider type/i }).selectOption(/gemini|google/i);
    await adminPage.getByLabel(/api key/i).fill('AIza-e2e-fake-gemini-key');
    await adminPage.getByRole('button', { name: /save|create/i }).click();
    await waitForToast(adminPage, /saved|created|success/i);
  });

  test('05 — register Vertex AI provider', async ({ adminPage }) => {
    await adminPage.goto('/settings');
    await adminPage.getByRole('button', { name: /add provider/i }).click();
    await adminPage.getByRole('dialog').waitFor();
    await adminPage.getByLabel(/name/i).fill('e2e-vertex');
    await adminPage.getByRole('combobox', { name: /type|provider type/i }).selectOption(/vertex/i);
    await adminPage.getByLabel(/project/i).fill('e2e-gcp-project');
    await adminPage.getByLabel(/region/i).fill('us-central1');
    await adminPage.getByRole('button', { name: /save|create/i }).click();
    await waitForToast(adminPage, /saved|created|success/i);
  });

  test('06 — register OpenRouter provider', async ({ adminPage }) => {
    await adminPage.goto('/settings');
    await adminPage.getByRole('button', { name: /add provider/i }).click();
    await adminPage.getByRole('dialog').waitFor();
    await adminPage.getByLabel(/name/i).fill('e2e-openrouter');
    await adminPage.getByRole('combobox', { name: /type|provider type/i }).selectOption(/openrouter/i);
    await adminPage.getByLabel(/api key/i).fill('sk-or-v1-e2e-fake-key');
    await adminPage.getByRole('button', { name: /save|create/i }).click();
    await waitForToast(adminPage, /saved|created|success/i);
  });

  test('07 — register Ollama provider and verify real ping', async ({ adminPage }) => {
    await adminPage.goto('/settings');
    await adminPage.getByRole('button', { name: /add provider/i }).click();
    await adminPage.getByRole('dialog').waitFor();
    await adminPage.getByLabel(/name/i).fill('e2e-ollama');
    await adminPage.getByRole('combobox', { name: /type|provider type/i }).selectOption('ollama');
    await adminPage.getByLabel(/base url|host/i).fill(process.env.OLLAMA_BASE_URL ?? 'http://localhost:11434');
    await adminPage.getByRole('button', { name: /save|create/i }).click();
    await waitForToast(adminPage, /saved|created|success/i);

    // Verify real Ollama ping
    const ollamaRes = await fetch(`${process.env.OLLAMA_BASE_URL ?? 'http://localhost:11434'}/api/tags`);
    expect(ollamaRes.ok).toBe(true);
    const tags = await ollamaRes.json();
    expect(tags.models).toBeDefined();
  });

  test('08 — Ollama models appear in model catalog', async ({ adminPage }) => {
    await navTo(adminPage, 'models');
    await expect(adminPage.getByText(/ollama/i).first()).toBeVisible({ timeout: 10_000 });
  });

  test('09 — LiteLLM fake provider from setup is listed', async ({ adminPage }) => {
    await adminPage.goto('/settings');
    await expect(adminPage.getByText('e2e-litellm-fake')).toBeVisible();
  });

  test('10 — deregister OpenRouter and confirm removed', async ({ adminPage }) => {
    await adminPage.goto('/settings');
    const row = adminPage.getByRole('row').filter({ hasText: 'e2e-openrouter' });
    await row.getByRole('button', { name: /delete|remove|deregister/i }).click();
    const dialog = adminPage.getByRole('dialog');
    if (await dialog.isVisible()) {
      await dialog.getByRole('button', { name: /confirm|delete|yes/i }).click();
    }
    await waitForToast(adminPage, /deleted|removed/i);
    await expect(adminPage.getByText('e2e-openrouter')).not.toBeVisible();
  });
});
