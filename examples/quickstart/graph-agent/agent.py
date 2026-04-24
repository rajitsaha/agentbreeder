"""Graph Agent — LangGraph implementation.

Queries the Neo4j knowledge graph to answer questions about
agent/tool/provider relationships.
Deployed by: agentbreeder deploy --target local
Chat with:   agentbreeder chat graph-agent
"""

from __future__ import annotations

import json
import os
from typing import Annotated, TypedDict

import httpx
from langchain_core.messages import BaseMessage, SystemMessage
from langchain_core.tools import tool
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode

NEO4J_HTTP = os.environ.get("NEO4J_HTTP_URL", "http://localhost:7474")
NEO4J_USER = os.environ.get("NEO4J_USER", "neo4j")
NEO4J_PASS = os.environ.get("NEO4J_PASSWORD", "agentbreeder")


# ── Tool: graph_query ───────────────────────────────────────────────────────

# Natural-language → Cypher template patterns
_NL_TO_CYPHER = {
    "which agents use": (
        "MATCH (a:Agent)-[:USES_TOOL]->(t:Tool) "
        "WHERE toLower(t.name) CONTAINS toLower('{keyword}') OR toLower(t.backend) CONTAINS toLower('{keyword}') "
        "RETURN a.name AS agent, t.name AS tool, t.description AS description"
    ),
    "what tools does": (
        "MATCH (a:Agent)-[:USES_TOOL]->(t:Tool) "
        "WHERE toLower(a.name) CONTAINS toLower('{keyword}') "
        "RETURN t.name AS tool, t.type AS type, t.description AS description"
    ),
    "which providers": (
        "MATCH (a:Agent)-[r:CALLS_PROVIDER]->(p:Provider) "
        "WHERE toLower(p.name) CONTAINS toLower('{keyword}') OR '{keyword}' = '' "
        "RETURN a.name AS agent, p.name AS provider, r.role AS role"
    ),
    "which frameworks": (
        "MATCH (f:Framework) WHERE f.tool_calling = true RETURN f.name AS framework, f.tool_calling AS tool_calling"
    ),
    "show me all agents": (
        "MATCH (a:Agent) RETURN a.name AS name, a.team AS team, a.status AS status, a.endpoint AS endpoint"
    ),
    "how is": (
        "MATCH (a:Agent)-[r]->(b) "
        "WHERE toLower(a.name) CONTAINS toLower('{keyword}') "
        "RETURN type(r) AS relationship, labels(b)[0] AS target_type, b.name AS target"
    ),
    "local": (
        "MATCH (p:Provider) WHERE p.local = true RETURN p.name AS provider, p.models AS models"
    ),
    "free": (
        "MATCH (p:Provider) WHERE p.free_tier = true RETURN p.name AS provider, p.local AS local, p.models AS models"
    ),
}


def _extract_keyword(question: str, prefix: str) -> str:
    """Very simple keyword extraction from a natural-language question."""
    lower = question.lower()
    idx = lower.find(prefix.lower())
    if idx == -1:
        return ""
    after = question[idx + len(prefix) :].strip()
    # Take first word or phrase up to a stop word
    words = after.split()
    keyword_words = []
    for w in words:
        if w.lower() in ("?", "the", "a", "an", "in", "on", "with", "for", "and", "or"):
            break
        keyword_words.append(w.strip("?.,!"))
    return " ".join(keyword_words)


def _nl_to_cypher(question: str) -> str:
    """Map a natural-language question to a Cypher query."""
    lower = question.lower()
    for pattern, cypher_template in _NL_TO_CYPHER.items():
        if pattern in lower:
            keyword = _extract_keyword(question, pattern)
            return cypher_template.format(keyword=keyword)
    # Fallback: return all agents
    return "MATCH (a:Agent) RETURN a.name AS name, a.team AS team, a.status AS status LIMIT 20"


@tool
def graph_query(question: str) -> str:
    """Query the Neo4j knowledge graph using natural language.

    Converts natural-language questions about agents, tools, and providers
    into Cypher queries and returns the results.

    Args:
        question: Natural language question, e.g.:
            - "Which agents use ChromaDB?"
            - "What tools does the search-agent have?"
            - "Which providers are free and local?"
            - "Show me all agents in the quickstart team"
            - "How is the a2a-orchestrator connected to other agents?"

    Returns:
        JSON string with query results.
    """
    cypher = _nl_to_cypher(question)

    try:
        resp = httpx.post(
            f"{NEO4J_HTTP}/db/neo4j/tx/commit",
            json={"statements": [{"statement": cypher}]},
            auth=(NEO4J_USER, NEO4J_PASS),
            timeout=15.0,
        )
        data = resp.json()
        errors = data.get("errors", [])
        if errors:
            return json.dumps(
                {"error": errors[0].get("message", "Unknown error"), "cypher": cypher}
            )

        results = data.get("results", [{}])[0]
        columns = results.get("columns", [])
        rows = [dict(zip(columns, row["row"])) for row in results.get("data", [])]

        return json.dumps(
            {
                "question": question,
                "cypher_used": cypher,
                "total_results": len(rows),
                "results": rows,
            },
            indent=2,
        )
    except httpx.ConnectError:
        return json.dumps(
            {
                "error": f"Cannot connect to Neo4j at {NEO4J_HTTP}. "
                "Is the quickstart stack running? Run: agentbreeder up"
            }
        )
    except Exception as exc:
        return json.dumps({"error": str(exc)})


# ── LangGraph state + graph ─────────────────────────────────────────────────


class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]


tools = [graph_query]
tool_node = ToolNode(tools)


def _build_llm():
    ollama_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
    model_name = os.environ.get("AGENT_MODEL", "llama3.2")
    try:
        resp = httpx.get(f"{ollama_url}/", timeout=3.0)
        if resp.status_code == 200:
            from langchain_ollama import ChatOllama

            return ChatOllama(model=model_name, base_url=ollama_url).bind_tools(tools)
    except Exception:
        pass
    if os.environ.get("ANTHROPIC_API_KEY"):
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(model="claude-haiku-4-20250414").bind_tools(tools)
    if os.environ.get("OPENAI_API_KEY"):
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(model="gpt-4o-mini").bind_tools(tools)
    litellm_url = os.environ.get("LITELLM_BASE_URL", "http://localhost:4000")
    from langchain_openai import ChatOpenAI

    return ChatOpenAI(
        model=f"ollama/{model_name}",
        base_url=f"{litellm_url}/v1",
        api_key=os.environ.get("LITELLM_MASTER_KEY", "sk-agentbreeder-quickstart"),
    ).bind_tools(tools)


SYSTEM_PROMPT = """You are a graph intelligence assistant connected to a Neo4j knowledge graph
about AI agents, their tools, frameworks, and providers.

Use graph_query for questions about:
- Which agents use a particular tool or provider
- What tools or frameworks a specific agent has
- Relationships between agents (A2A connections)
- Which providers are local/free
- All agents in a team

Example questions you can answer well:
- "Which agents use ChromaDB?"
- "What tools does the search-agent have?"
- "Which frameworks support tool calling?"
- "Show me all agents in the quickstart team"
- "How is the a2a-orchestrator connected to other agents?"
- "Which providers are free and run locally?"

Always call graph_query first, then explain the results in plain English.
If results are empty, say the graph may not have that information yet.
"""


def call_model(state: AgentState) -> AgentState:
    llm = _build_llm()
    messages = [SystemMessage(content=SYSTEM_PROMPT)] + state["messages"]
    response = llm.invoke(messages)
    return {"messages": [response]}


def should_continue(state: AgentState) -> str:
    last = state["messages"][-1]
    if hasattr(last, "tool_calls") and last.tool_calls:
        return "tools"
    return END


builder = StateGraph(AgentState)
builder.add_node("agent", call_model)
builder.add_node("tools", tool_node)
builder.set_entry_point("agent")
builder.add_conditional_edges("agent", should_continue, {"tools": "tools", END: END})
builder.add_edge("tools", "agent")

graph = builder.compile()
