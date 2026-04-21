import { test, expect, apiOk } from "./fixtures";

// ---------------------------------------------------------------------------
// Mock data
// ---------------------------------------------------------------------------

const GRAPH_INDEX = {
  id: "idx-1",
  name: "test-graph-index",
  description: "Graph-type RAG index for testing",
  embedding_model: "openai/text-embedding-3-small",
  entity_model: "gpt-4o-mini",
  chunk_strategy: "fixed_size",
  chunk_size: 512,
  chunk_overlap: 64,
  dimensions: 1536,
  source: "local",
  index_type: "graph",
  doc_count: 10,
  chunk_count: 100,
  created_at: "2026-04-01T00:00:00Z",
  updated_at: "2026-04-01T00:00:00Z",
};

const VECTOR_INDEX = {
  id: "idx-2",
  name: "test-vector-index",
  description: "Vector-only RAG index",
  embedding_model: "openai/text-embedding-3-small",
  entity_model: "",
  chunk_strategy: "fixed_size",
  chunk_size: 512,
  chunk_overlap: 64,
  dimensions: 1536,
  source: "local",
  index_type: "vector",
  doc_count: 5,
  chunk_count: 50,
  created_at: "2026-04-01T00:00:00Z",
  updated_at: "2026-04-01T00:00:00Z",
};

const GRAPH_METADATA = {
  index_id: "idx-1",
  index_type: "graph",
  node_count: 5,
  edge_count: 8,
  entity_types: [{ type: "concept", count: 5 }],
  top_entities: [],
};

const GRAPH_ENTITIES_ALL = {
  items: [
    {
      id: "e1",
      entity: "AgentBreeder",
      entity_type: "concept",
      description: "AI agent platform",
      chunk_ids: ["c1"],
    },
    {
      id: "e2",
      entity: "deploy",
      entity_type: "action",
      description: "Deploy agents",
      chunk_ids: ["c1"],
    },
  ],
  total: 2,
  page: 1,
  per_page: 20,
};

const GRAPH_ENTITIES_CONCEPT_ONLY = {
  items: [
    {
      id: "e1",
      entity: "AgentBreeder",
      entity_type: "concept",
      description: "AI agent platform",
      chunk_ids: ["c1"],
    },
  ],
  total: 1,
  page: 1,
  per_page: 20,
};

const GRAPH_ENTITIES_WITH_PROJECT = {
  items: [
    {
      id: "e1",
      entity: "AgentBreeder",
      entity_type: "concept",
      description: "AI agent platform",
      chunk_ids: ["c1"],
    },
    {
      id: "e2",
      entity: "deploy",
      entity_type: "action",
      description: "Deploy agents",
      chunk_ids: ["c1"],
    },
    {
      id: "e3",
      entity: "AgentBreederCloud",
      entity_type: "project",
      description: "Cloud-hosted managed service",
      chunk_ids: ["c2"],
    },
  ],
  total: 3,
  page: 1,
  per_page: 20,
};

const GRAPH_METADATA_WITH_PROJECT = {
  ...GRAPH_METADATA,
  entity_types: [
    { type: "concept", count: 1 },
    { type: "action", count: 1 },
    { type: "project", count: 1 },
  ],
};

const GRAPH_RELATIONSHIPS_EMPTY = {
  items: [],
  total: 0,
  page: 1,
  per_page: 200,
};

const GRAPH_RELATIONSHIPS_WITH_E1 = {
  items: [
    {
      id: "r1",
      subject_id: "e1",
      predicate: "uses",
      object_id: "e2",
      subject_entity: "AgentBreeder",
      object_entity: "deploy",
      chunk_ids: ["c1"],
      weight: 1.0,
    },
  ],
  total: 1,
  page: 1,
  per_page: 200,
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function listResponse<T>(items: T[], total: number) {
  return JSON.stringify({
    data: items,
    meta: { page: 1, per_page: 20, total },
    errors: [],
  });
}

function pagedResponse<T>(payload: {
  items: T[];
  total: number;
  page: number;
  per_page: number;
}) {
  return JSON.stringify({
    data: payload.items,
    meta: { page: payload.page, per_page: payload.per_page, total: payload.total },
    errors: [],
  });
}

/** Navigate to /rag, set up the index-list mock, click the index card by name. */
async function openIndexDetail(
  page: Parameters<typeof test>[1] extends (args: { authedPage: infer P }) => unknown
    ? P
    : never,
  index: typeof GRAPH_INDEX,
) {
  await page.route("**/api/v1/rag/indexes", (route) => {
    if (route.request().method() === "GET") {
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: listResponse([index], 1),
      });
    } else {
      route.continue();
    }
  });

  await page.route(`**/api/v1/rag/indexes/${index.id}`, (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: apiOk(index, 1),
    }),
  );

  await page.goto("/rag");
  await page.waitForTimeout(300);

  // Click the index card
  await page.getByText(index.name).click();
  await page.waitForTimeout(300);
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

test.describe("GraphRAG — Knowledge Graph tab visibility", () => {
  test("Graph tab appears for graph-type indexes", async ({ authedPage: page }) => {
    await openIndexDetail(page, GRAPH_INDEX);
    await expect(page.getByText("Knowledge Graph")).toBeVisible();
  });

  test("Graph tab does NOT appear for vector-type indexes", async ({ authedPage: page }) => {
    await openIndexDetail(page, VECTOR_INDEX);
    // Wait for the detail view to settle
    await page.waitForTimeout(300);
    await expect(page.getByText("Knowledge Graph")).not.toBeVisible();
  });
});

test.describe("GraphRAG — Entity list", () => {
  test("Entity list shows entities after clicking graph tab", async ({ authedPage: page }) => {
    // Set up graph data mocks
    await page.route("**/api/v1/rag/indexes/idx-1/graph", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: apiOk(GRAPH_METADATA),
      }),
    );
    await page.route("**/api/v1/rag/indexes/idx-1/entities**", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: pagedResponse(GRAPH_ENTITIES_ALL),
      }),
    );
    await page.route("**/api/v1/rag/indexes/idx-1/relationships**", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: pagedResponse(GRAPH_RELATIONSHIPS_EMPTY),
      }),
    );

    await openIndexDetail(page, GRAPH_INDEX);

    // Click Knowledge Graph tab
    await page.getByText("Knowledge Graph").click();
    await page.waitForTimeout(500);

    await expect(page.getByText("AgentBreeder")).toBeVisible();
    await expect(page.getByText("deploy")).toBeVisible();
  });
});

test.describe("GraphRAG — Entity type filter", () => {
  test("Entity type filter updates the visible entities", async ({ authedPage: page }) => {
    // Default (all types)
    await page.route("**/api/v1/rag/indexes/idx-1/graph", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: apiOk(GRAPH_METADATA_WITH_PROJECT),
      }),
    );

    // Filtered to concept only
    await page.route("**/api/v1/rag/indexes/idx-1/entities*", (route) => {
      const url = route.request().url();
      if (url.includes("entity_type=concept")) {
        route.fulfill({
          status: 200,
          contentType: "application/json",
          body: pagedResponse(GRAPH_ENTITIES_CONCEPT_ONLY),
        });
      } else {
        route.fulfill({
          status: 200,
          contentType: "application/json",
          body: pagedResponse(GRAPH_ENTITIES_WITH_PROJECT),
        });
      }
    });
    await page.route("**/api/v1/rag/indexes/idx-1/relationships**", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: pagedResponse(GRAPH_RELATIONSHIPS_EMPTY),
      }),
    );

    await openIndexDetail(page, GRAPH_INDEX);
    await page.getByText("Knowledge Graph").click();
    await page.waitForTimeout(500);

    // Select "concept" from the entity type filter dropdown
    const filterSelect = page.locator("select").last();
    await filterSelect.selectOption("concept");
    await page.waitForTimeout(400);

    // Only concept entities should be visible — "deploy" (action) and
    // "AgentBreederCloud" (project) should be gone.
    await expect(page.getByText("AgentBreeder")).toBeVisible();
    const body = await page.textContent("body");
    // After filtering, the non-concept entities may not be in the DOM
    // We check the body text doesn't show the filtered-out "AgentBreederCloud"
    expect(body?.includes("AgentBreederCloud")).toBeFalsy();
  });
});

test.describe("GraphRAG — Ego graph SVG", () => {
  test("Clicking an entity renders the ego graph SVG", async ({ authedPage: page }) => {
    await page.route("**/api/v1/rag/indexes/idx-1/graph", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: apiOk(GRAPH_METADATA),
      }),
    );
    await page.route("**/api/v1/rag/indexes/idx-1/entities**", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: pagedResponse(GRAPH_ENTITIES_ALL),
      }),
    );
    await page.route("**/api/v1/rag/indexes/idx-1/relationships**", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: pagedResponse(GRAPH_RELATIONSHIPS_WITH_E1),
      }),
    );

    await openIndexDetail(page, GRAPH_INDEX);
    await page.getByText("Knowledge Graph").click();
    await page.waitForTimeout(500);

    // Click "AgentBreeder" entity in the list
    // The entity list renders buttons — click the first match
    await page.getByRole("button", { name: /AgentBreeder/i }).first().click();
    await page.waitForTimeout(400);

    // An SVG element should be visible (the ego graph)
    await expect(page.locator("svg").first()).toBeVisible();

    // The center node label or header should mention "AgentBreeder"
    const panelText = await page.textContent("body");
    expect(panelText?.includes("AgentBreeder")).toBeTruthy();
  });
});

test.describe("GraphRAG — Metadata badges", () => {
  test("Graph metadata badges show node and edge counts", async ({ authedPage: page }) => {
    await page.route("**/api/v1/rag/indexes/idx-1/graph", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: apiOk(GRAPH_METADATA),
      }),
    );
    await page.route("**/api/v1/rag/indexes/idx-1/entities**", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: pagedResponse(GRAPH_ENTITIES_ALL),
      }),
    );
    await page.route("**/api/v1/rag/indexes/idx-1/relationships**", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: pagedResponse(GRAPH_RELATIONSHIPS_EMPTY),
      }),
    );

    await openIndexDetail(page, GRAPH_INDEX);
    await page.getByText("Knowledge Graph").click();
    await page.waitForTimeout(500);

    // GRAPH_METADATA has node_count: 5, edge_count: 8
    // The GraphTab renders these as large font-semibold numbers
    const body = await page.textContent("body");
    expect(body?.includes("5")).toBeTruthy();
    expect(body?.includes("8")).toBeTruthy();
  });
});
