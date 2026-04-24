"""RAG Agent — LangGraph implementation.

Searches ChromaDB for relevant context before answering.
Deployed by: agentbreeder deploy --target local
Chat with:   agentbreeder chat rag-agent
"""

from __future__ import annotations

import json
import os
from typing import Annotated, TypedDict

import httpx
from langchain_core.messages import BaseMessage
from langchain_core.tools import tool
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode

CHROMADB_URL = os.environ.get("CHROMADB_URL", "http://localhost:8001")
COLLECTION = os.environ.get("COLLECTION_NAME", "agentbreeder_knowledge")


# ── Tool: rag_search ────────────────────────────────────────────────────────


@tool
def rag_search(query: str, n_results: int = 3) -> str:
    """Search the AgentBreeder knowledge base using semantic vector search.

    Args:
        query: The question or topic to search for.
        n_results: Number of results to return (default 3).

    Returns:
        JSON string with matched documents and their metadata.
    """
    try:
        # Get collection ID
        resp = httpx.get(f"{CHROMADB_URL}/api/v1/collections/{COLLECTION}", timeout=10.0)
        if resp.status_code != 200:
            return json.dumps(
                {"error": f"Collection '{COLLECTION}' not found. Run: agentbreeder seed"}
            )
        collection_id = resp.json()["id"]

        # Query by embedding (ChromaDB embeds the query automatically)
        resp = httpx.post(
            f"{CHROMADB_URL}/api/v1/collections/{collection_id}/query",
            json={
                "query_texts": [query],
                "n_results": n_results,
                "include": ["documents", "metadatas", "distances"],
            },
            timeout=30.0,
        )
        if resp.status_code != 200:
            return json.dumps({"error": f"Query failed: HTTP {resp.status_code}"})

        data = resp.json()
        documents = data.get("documents", [[]])[0]
        metadatas = data.get("metadatas", [[]])[0]
        distances = data.get("distances", [[]])[0]

        results = []
        for doc, meta, dist in zip(documents, metadatas, distances):
            results.append(
                {
                    "text": doc,
                    "source": meta.get("source", "unknown"),
                    "topic": meta.get("topic", ""),
                    "relevance_score": round(1 - dist, 3),  # convert distance → similarity
                }
            )

        return json.dumps({"results": results, "total": len(results)}, indent=2)

    except httpx.ConnectError:
        return json.dumps(
            {
                "error": f"Cannot connect to ChromaDB at {CHROMADB_URL}. "
                "Is the quickstart stack running? Run: agentbreeder up"
            }
        )
    except Exception as exc:
        return json.dumps({"error": str(exc)})


# ── LangGraph state + graph ─────────────────────────────────────────────────


class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]


tools = [rag_search]
tool_node = ToolNode(tools)


def _build_llm():
    """Build the LLM, preferring Ollama → Anthropic → OpenAI."""
    ollama_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
    model_name = os.environ.get("AGENT_MODEL", "llama3.2")

    # Try Ollama first (free, local)
    try:
        resp = httpx.get(f"{ollama_url}/", timeout=3.0)
        if resp.status_code == 200:
            from langchain_ollama import ChatOllama

            return ChatOllama(model=model_name, base_url=ollama_url).bind_tools(tools)
    except Exception:
        pass

    # Try Anthropic
    if os.environ.get("ANTHROPIC_API_KEY"):
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(model="claude-haiku-4-20250414").bind_tools(tools)

    # Try OpenAI
    if os.environ.get("OPENAI_API_KEY"):
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(model="gpt-4o-mini").bind_tools(tools)

    # Try LiteLLM gateway
    litellm_url = os.environ.get("LITELLM_BASE_URL", "http://localhost:4000")
    from langchain_openai import ChatOpenAI

    return ChatOpenAI(
        model=f"ollama/{model_name}",
        base_url=f"{litellm_url}/v1",
        api_key=os.environ.get("LITELLM_MASTER_KEY", "sk-agentbreeder-quickstart"),
    ).bind_tools(tools)


SYSTEM_PROMPT = """You are a helpful AI assistant with access to the AgentBreeder knowledge base.

Use the rag_search tool to find relevant information BEFORE answering any question.
Always:
1. Search for relevant context first
2. Base your answer on the search results
3. Cite which document(s) you used (use the 'source' field)
4. If search returns no results, say so clearly

You specialize in questions about:
- AgentBreeder features and configuration
- The agent.yaml specification
- Deployment to AWS, GCP, Azure, Kubernetes, local Docker
- Supported frameworks (LangGraph, CrewAI, Claude SDK, etc.)
- RAG, GraphRAG, MCP servers, A2A communication
"""


def call_model(state: AgentState) -> AgentState:
    llm = _build_llm()
    from langchain_core.messages import SystemMessage

    messages = [SystemMessage(content=SYSTEM_PROMPT)] + state["messages"]
    response = llm.invoke(messages)
    return {"messages": [response]}


def should_continue(state: AgentState) -> str:
    last = state["messages"][-1]
    if hasattr(last, "tool_calls") and last.tool_calls:
        return "tools"
    return END


# Build and export the graph
builder = StateGraph(AgentState)
builder.add_node("agent", call_model)
builder.add_node("tools", tool_node)
builder.set_entry_point("agent")
builder.add_conditional_edges("agent", should_continue, {"tools": "tools", END: END})
builder.add_edge("tools", "agent")

graph = builder.compile()
