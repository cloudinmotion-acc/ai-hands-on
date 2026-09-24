"""
P5 agent — LangGraph ReAct agent that uses the MCP search_products tool.

The agent receives a user shopping query, calls search_products() via the
in-process MCP bridge, then synthesises a friendly natural-language response
with a product recommendation list.

Note: we call the search pipeline directly (function import) rather than
spawning a separate MCP subprocess — this keeps the demo simple and avoids
an extra process. The MCP server is still available as a standalone process
for any external MCP client.
"""

import asyncio
import os
from pathlib import Path
from typing import Annotated, Any

import httpx
from dotenv import load_dotenv
from langchain_core.messages import SystemMessage, AIMessage, ToolMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict

# Import the MCP tool logic directly (in-process bridge)
from mcp_server import search_products as _search_products_impl

load_dotenv(Path(__file__).parent / ".env")

_AGENT_MODEL = os.environ.get("AGENT_MODEL", "nvidia/nemotron-3-super-120b-a12b")
_BASE_URL    = os.environ.get("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1")
_API_KEY     = os.environ["NVIDIA_API_KEY"]

SYSTEM_PROMPT = """You are a helpful shopping assistant for a clothing store that sells kids, teens, women's, and men's clothing.

IMPORTANT: Call search_products EXACTLY ONCE per user request. Never call it more than once.

When a user asks to find a product:
1. Call search_products once with their exact query.
2. From the results, pick the top 3–5 most relevant products.
3. Present each with: name, price (₹), size, colour, fabric, in-stock status, and a one-sentence description.
4. Give a brief recommendation at the end.

If no products match, apologise and suggest the user broaden their search.
Keep your tone friendly and conversational."""


# ── LangChain tool wrapper ────────────────────────────────────────────────────

@tool
def search_products(query: str, top_k: int = 10) -> str:
    """
    Search the product catalogue using a hybrid pipeline (SQL + BM25 + pgvector).
    Pass the user's shopping query exactly as they typed it.
    """
    return _search_products_impl(query=query, top_k=top_k)


TOOLS = [search_products]


# ── LangGraph state ───────────────────────────────────────────────────────────

class AgentState(TypedDict):
    messages: Annotated[list, add_messages]


# ── Node helpers ──────────────────────────────────────────────────────────────

def _make_llm() -> ChatOpenAI:
    return ChatOpenAI(
        model=_AGENT_MODEL,
        base_url=_BASE_URL,
        api_key=_API_KEY,
        temperature=0.1,
        http_client=httpx.Client(verify=False),
        http_async_client=httpx.AsyncClient(verify=False),
    )


async def agent_node(state: AgentState) -> dict:
    llm = _make_llm()
    llm_with_tools = llm.bind_tools(TOOLS)

    messages = state["messages"]
    if not any(isinstance(m, SystemMessage) for m in messages):
        messages = [SystemMessage(content=SYSTEM_PROMPT)] + list(messages)

    for attempt in range(4):
        try:
            response = await llm_with_tools.ainvoke(messages)
            return {"messages": [response]}
        except Exception as exc:
            is_overload = any(
                kw in str(exc)
                for kw in ("overloaded", "temporarily", "Service temporarily")
            )
            if is_overload and attempt < 3:
                wait = 5 * (2 ** attempt)
                await asyncio.sleep(wait)
                continue
            raise


def tool_node(state: AgentState) -> dict:
    """Execute all pending tool calls synchronously."""
    last_msg = state["messages"][-1]
    tool_map = {t.name: t for t in TOOLS}

    results = []
    for call in last_msg.tool_calls:
        fn = tool_map.get(call["name"])
        if fn is None:
            output = f"Unknown tool: {call['name']}"
        else:
            try:
                output = fn.invoke(call["args"])
            except Exception as e:
                output = f"Tool error: {e}"

        results.append(
            ToolMessage(
                content=str(output),
                tool_call_id=call["id"],
                name=call["name"],
            )
        )

    return {"messages": results}


def should_continue(state: AgentState) -> str:
    last = state["messages"][-1]
    if isinstance(last, AIMessage) and last.tool_calls:
        return "tools"
    return END


# ── Graph ─────────────────────────────────────────────────────────────────────

def build_graph() -> Any:
    g = StateGraph(AgentState)
    g.add_node("agent", agent_node)
    g.add_node("tools", tool_node)
    g.set_entry_point("agent")
    g.add_conditional_edges("agent", should_continue, {"tools": "tools", END: END})
    g.add_edge("tools", "agent")
    return g.compile()


GRAPH = build_graph()
