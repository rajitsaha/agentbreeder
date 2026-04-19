import { test as setup } from '@playwright/test';
import { writeFileSync, mkdirSync } from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

const API = process.env.E2E_API_BASE_URL ?? 'http://localhost:8000';
const ADMIN_EMAIL = process.env.E2E_ADMIN_EMAIL!;
const ADMIN_PASSWORD = process.env.E2E_ADMIN_PASSWORD!;
const MEMBER_EMAIL = process.env.E2E_MEMBER_EMAIL!;
const MEMBER_PASSWORD = process.env.E2E_MEMBER_PASSWORD!;
const VIEWER_EMAIL = process.env.E2E_VIEWER_EMAIL!;
const VIEWER_PASSWORD = process.env.E2E_VIEWER_PASSWORD!;

async function registerUser(email: string, password: string, name: string, team = 'e2e-team-alpha') {
  const res = await fetch(`${API}/api/v1/auth/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password, name, team }),
  });
  if (!res.ok && res.status !== 409 && res.status !== 400) {
    throw new Error(`Register failed for ${email}: ${res.status} ${await res.text()}`);
  }
}

async function loginUser(email: string, password: string): Promise<string> {
  const res = await fetch(`${API}/api/v1/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  });
  if (!res.ok) throw new Error(`Login failed for ${email}: ${res.status} ${await res.text()}`);
  const body = await res.json();
  return body.access_token ?? body.data?.access_token;
}

async function apiPost(path: string, token: string, body: unknown) {
  const res = await fetch(`${API}${path}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${token}`,
    },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`POST ${path} failed: ${res.status} ${await res.text()}`);
  const json = await res.json();
  return json.data ?? json;
}

setup('provision test users, teams, and provider', async ({ page }) => {
  // 1. Register all three users
  await registerUser(ADMIN_EMAIL, ADMIN_PASSWORD, 'E2E Admin', 'e2e-team-alpha');
  await registerUser(MEMBER_EMAIL, MEMBER_PASSWORD, 'E2E Member', 'e2e-team-alpha');
  await registerUser(VIEWER_EMAIL, VIEWER_PASSWORD, 'E2E Viewer', 'e2e-team-alpha');

  // 2. Login all three and save tokens
  const adminToken = await loginUser(ADMIN_EMAIL, ADMIN_PASSWORD);
  const memberToken = await loginUser(MEMBER_EMAIL, MEMBER_PASSWORD);
  const viewerToken = await loginUser(VIEWER_EMAIL, VIEWER_PASSWORD);

  // 3. Save admin browser auth state
  await page.goto('/');
  await page.evaluate((tok) => localStorage.setItem('ag-token', tok), adminToken);
  mkdirSync(path.resolve(__dirname, '../../../.auth'), { recursive: true });
  await page.context().storageState({ path: path.resolve(__dirname, '../../../.auth/admin.json') });

  // 4. Save member browser auth state
  await page.evaluate((tok) => localStorage.setItem('ag-token', tok), memberToken);
  await page.context().storageState({ path: path.resolve(__dirname, '../../../.auth/member.json') });

  // 5. Save viewer browser auth state
  await page.evaluate((tok) => localStorage.setItem('ag-token', tok), viewerToken);
  await page.context().storageState({ path: path.resolve(__dirname, '../../../.auth/viewer.json') });

  // 6. Create e2e-team-alpha
  let teamAlphaId: string;
  let teamBetaId: string;
  try {
    const alpha = await apiPost('/api/v1/teams', adminToken, { name: 'e2e-team-alpha' });
    teamAlphaId = alpha.id;
  } catch {
    const list = await fetch(`${API}/api/v1/teams`, {
      headers: { 'Authorization': `Bearer ${adminToken}` },
    }).then(r => r.json());
    const found = (list.data ?? list).find((t: { name: string; id: string }) => t.name === 'e2e-team-alpha');
    teamAlphaId = found?.id ?? 'unknown';
  }

  // 7. Create e2e-team-beta
  try {
    const beta = await apiPost('/api/v1/teams', adminToken, { name: 'e2e-team-beta' });
    teamBetaId = beta.id;
  } catch {
    const list = await fetch(`${API}/api/v1/teams`, {
      headers: { 'Authorization': `Bearer ${adminToken}` },
    }).then(r => r.json());
    const found = (list.data ?? list).find((t: { name: string; id: string }) => t.name === 'e2e-team-beta');
    teamBetaId = found?.id ?? 'unknown';
  }

  // 8. Register LiteLLM fake provider
  let litellmProviderId: string;
  try {
    const provider = await apiPost('/api/v1/providers', adminToken, {
      name: 'e2e-litellm-fake',
      type: 'litellm',
      base_url: 'http://localhost:4000',
      model: 'fake/gpt-4',
    });
    litellmProviderId = provider.id;
  } catch {
    litellmProviderId = 'seeded-in-prior-run';
  }

  // 9. Write shared state
  const state = {
    adminToken,
    memberToken,
    viewerToken,
    teamAlphaId,
    teamBetaId,
    litellmProviderId,
  };
  writeFileSync(
    path.resolve(__dirname, '../../../.e2e-state.json'),
    JSON.stringify(state, null, 2),
  );

  console.log('Global setup complete:', JSON.stringify({ teamAlphaId, teamBetaId, litellmProviderId }));
});
