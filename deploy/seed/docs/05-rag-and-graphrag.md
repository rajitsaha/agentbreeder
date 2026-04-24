# RAG and GraphRAG

## RAG with ChromaDB

AgentBreeder supports vector-based Retrieval-Augmented Generation via ChromaDB.

### Quickstart RAG setup

The quickstart stack spins up ChromaDB at `http://localhost:8001` and seeds the `agentbreeder_knowledge` collection with 10+ documents.

To seed more data yourself:
```bash
agentbreeder seed --chromadb --docs ./my-docs/
```

### Defining a RAG knowledge base in agent.yaml

```yaml
knowledge_bases:
  - name: my-docs
    type: chromadb
    collection: my_collection
    url: http://chromadb:8000

tools:
  - name: rag_search
    type: function
    description: "Search the knowledge base"
    schema:
      type: object
      properties:
        query: {type: string}
        n_results: {type: integer, default: 3}
      required: [query]
```

### The rag-agent example

The `rag-agent` in `examples/quickstart/rag-agent.yaml` is pre-configured to search the `agentbreeder_knowledge` ChromaDB collection:

```bash
agentbreeder chat rag-agent
# Ask: "How do I deploy an agent to AWS?"
# Ask: "What is the agent.yaml format?"
# Ask: "Which frameworks does AgentBreeder support?"
```

### ChromaDB collection details

| Collection | Documents | Topics |
|-----------|-----------|--------|
| agentbreeder_knowledge | 10+ | overview, agent.yaml, deployment, frameworks, RAG, GraphRAG, MCP, A2A |

### Adding your own documents

```bash
# Seed from a directory of markdown/text files
agentbreeder seed --chromadb --collection my-collection --docs ./docs/

# Seed from a single file
agentbreeder seed --chromadb --collection my-collection --file ./data.txt

# Check what's in a collection
agentbreeder seed --chromadb --list
```

## GraphRAG with Neo4j

AgentBreeder supports knowledge graph-based RAG via Neo4j Community.

### Quickstart GraphRAG setup

The quickstart stack spins up Neo4j at:
- Browser UI: http://localhost:7474 (login: neo4j / agentbreeder)
- Bolt: bolt://localhost:7687

The graph is seeded with nodes and relationships for agents, tools, frameworks, providers, and deploy targets.

### Sample queries the graph-agent can answer

- "Which agents use ChromaDB?"
- "What tools does the search-agent have?"
- "Which providers support local inference?"
- "Show me all agents in the quickstart team"
- "What frameworks support tool calling?"
- "How is the a2a-orchestrator connected to other agents?"

### Adding to the knowledge graph

```bash
# Re-seed with the default graph
agentbreeder seed --neo4j

# Run a custom Cypher file
agentbreeder seed --neo4j --cypher ./my-graph.cypher
```

### Graph schema (quickstart)

Nodes: `Agent`, `Tool`, `Framework`, `Provider`, `DeployTarget`

Relationships:
- `(Agent)-[:RUNS_ON]->(Framework)`
- `(Agent)-[:USES_TOOL]->(Tool)`
- `(Agent)-[:CALLS_PROVIDER]->(Provider)`
- `(Agent)-[:CALLS_AGENT]->(Agent)` ← A2A relationships
- `(Agent)-[:DEPLOYED_ON]->(DeployTarget)`
