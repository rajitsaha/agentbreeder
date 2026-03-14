import { test, expect } from "./fixtures";

const MOCK_EVAL_DATASET = {
  id: "ds-0001",
  name: "support-qa-v1",
  description: "Q&A pairs for support agent",
  agent_id: "aaaaaaaa-0000-0000-0000-000000000001",
  row_count: 50,
  created_at: "2026-03-01T00:00:00Z",
};

const MOCK_EVAL_RUN = {
  id: "run-0001",
  dataset_id: "ds-0001",
  agent_id: "aaaaaaaa-0000-0000-0000-000000000001",
  agent_name: "customer-support-agent",
  status: "completed",
  pass_count: 45,
  fail_count: 5,
  total_count: 50,
  pass_rate: 0.9,
  avg_latency_ms: 800,
  total_cost_usd: 0.25,
  started_at: "2026-03-10T09:00:00Z",
  completed_at: "2026-03-10T09:05:00Z",
};

function makeDatasetsResponse(datasets: typeof MOCK_EVAL_DATASET[]) {
  return {
    data: datasets,
    meta: { page: 1, per_page: 20, total: datasets.length },
    errors: [],
  };
}

function makeRunsResponse(runs: typeof MOCK_EVAL_RUN[]) {
  return {
    data: runs,
    meta: { page: 1, per_page: 20, total: runs.length },
    errors: [],
  };
}

test.describe("Eval Datasets Page", () => {
  test("renders eval datasets page", async ({ authedPage: page }) => {
    await page.route("**/api/v1/eval/datasets**", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(makeDatasetsResponse([])),
      })
    );
    await page.goto("/evals/datasets");
    await page.waitForTimeout(500);
    const body = await page.textContent("body");
    expect(body?.toLowerCase()).toContain("dataset");
  });

  test("shows dataset cards when data", async ({ authedPage: page }) => {
    await page.route("**/api/v1/eval/datasets**", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(makeDatasetsResponse([MOCK_EVAL_DATASET])),
      })
    );
    await page.goto("/evals/datasets");
    await page.waitForTimeout(500);
    await expect(page.getByText("support-qa-v1")).toBeVisible();
  });

  test("new dataset button visible on datasets page", async ({ authedPage: page }) => {
    await page.route("**/api/v1/eval/datasets**", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(makeDatasetsResponse([])),
      })
    );
    await page.goto("/evals/datasets");
    await page.waitForTimeout(500);
    const newButton = page
      .getByRole("button", { name: /new/i })
      .or(page.getByRole("button", { name: /create/i }))
      .or(page.getByRole("button", { name: /dataset/i }))
      .first();
    await expect(newButton).toBeVisible();
  });
});

test.describe("Eval Runs Page", () => {
  test("renders eval runs page", async ({ authedPage: page }) => {
    await page.route("**/api/v1/eval/runs**", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(makeRunsResponse([])),
      })
    );
    await page.goto("/evals/runs");
    await page.waitForTimeout(500);
    const body = await page.textContent("body");
    expect(body?.toLowerCase()).toContain("run");
  });

  test("shows run cards with pass rate", async ({ authedPage: page }) => {
    await page.route("**/api/v1/eval/runs**", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(makeRunsResponse([MOCK_EVAL_RUN])),
      })
    );
    await page.goto("/evals/runs");
    await page.waitForTimeout(500);
    const body = await page.textContent("body");
    expect(
      body?.includes("customer-support-agent") ||
        body?.includes("90%") ||
        body?.includes("90")
    ).toBeTruthy();
  });

  test("eval runs show status badge", async ({ authedPage: page }) => {
    await page.route("**/api/v1/eval/runs**", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(makeRunsResponse([MOCK_EVAL_RUN])),
      })
    );
    await page.goto("/evals/runs");
    await page.waitForTimeout(500);
    const body = await page.textContent("body");
    expect(body?.toLowerCase()).toContain("completed");
  });
});
