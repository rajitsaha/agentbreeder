/**
 * Thin HTTP client that talks to the real AgentBreeder API.
 * Used by E2E Docker tests to set up real state before UI assertions.
 */

const BASE = process.env.PLAYWRIGHT_DOCKER_BASE_URL ?? "http://localhost:3001";
const API = `${BASE}/api/v1`;

export interface UserCreds {
  email: string;
  password: string;
  name: string;
  team: string;
}

export interface AuthTokens {
  access_token: string;
  token_type: string;
}

/** Register a new user. Throws if status != 201. */
export async function registerUser(creds: UserCreds): Promise<void> {
  const res = await fetch(`${API}/auth/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(creds),
  });
  if (res.status !== 201) {
    const body = await res.text();
    throw new Error(`registerUser failed ${res.status}: ${body}`);
  }
}

/** Login and return access token. Throws if status != 200. */
export async function loginUser(
  email: string,
  password: string,
): Promise<AuthTokens> {
  const res = await fetch(`${API}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`loginUser failed ${res.status}: ${body}`);
  }
  const json = await res.json();
  return json.data as AuthTokens;
}

/** Create an agent. Returns the created agent's id. */
export async function createAgent(
  token: string,
  payload: {
    name: string;
    version: string;
    team: string;
    owner: string;
    framework: string;
    model_primary: string;
  },
): Promise<string> {
  const res = await fetch(`${API}/agents`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`createAgent failed ${res.status}: ${body}`);
  }
  const json = await res.json();
  return json.data.id as string;
}

/** Generate a unique test email to avoid conflicts between test runs. */
export function uniqueEmail(prefix = "e2e"): string {
  return `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2, 7)}@test.local`;
}
