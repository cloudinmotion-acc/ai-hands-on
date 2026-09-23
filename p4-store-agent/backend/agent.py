"""
P4 Store Agent — LangGraph Definition

Architecture:
  START → [agent] → (tool_calls?) → [tools] → [agent] → ... → END

State:
  messages  – full conversation history (LangGraph reducer merges lists)
  trace     – our custom step-by-step log streamed to the UI

The agent node binds all three tools to the LLM. On each turn:
  • If the LLM emits tool_calls  → route to [tools] node (ToolNode)
  • If the LLM emits plain text  → route to END (final answer)
"""

import asyncio
import os
from typing import Annotated
from dotenv import load_dotenv

import httpx
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, BaseMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition
from typing_extensions import TypedDict

from tools import check_stock, price_order, delivery_eta

load_dotenv()

# ── State ──────────────────────────────────────────────────────────────────────

class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]


# ── LLM ────────────────────────────────────────────────────────────────────────

def _make_llm(model: str | None = None) -> ChatOpenAI:
    return ChatOpenAI(
        model=model or os.getenv("AGENT_MODEL", "nvidia/nemotron-3-super-120b-a12b"),
        base_url=os.getenv("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1"),
        api_key=os.getenv("NVIDIA_API_KEY"),
        temperature=0.1,
        http_client=httpx.Client(verify=False),
        http_async_client=httpx.AsyncClient(verify=False),
    )


TOOLS = [check_stock, price_order, delivery_eta]

SYSTEM_PROMPT = """You are a helpful store assistant for an online clothing retailer.

When a customer makes a request, you MUST follow this exact sequence using your tools:
1. check_stock  — verify the item is available in the requested quantity
2. price_order  — calculate the total price with any applicable discount
3. delivery_eta — look up the estimated delivery date for the pincode

Rules:
- If check_stock returns in_stock=false, stop immediately and tell the customer the item is out of stock. Do NOT call price_order or delivery_eta.
- If any tool returns an error, explain it clearly and stop.
- Always pass the exact SKU and unit_price from check_stock into price_order.
- If the customer does not specify express or standard shipping, use standard.
- Present the final answer clearly: stock status, final price (with discount if any), and delivery date.
- Use INR (₹) for all prices.
- Be concise and friendly.
"""


# ── Nodes ───────────────────────────────────────────────────────────────────────

async def agent_node(state: AgentState, config: RunnableConfig) -> dict:
    """LLM decides: call a tool or produce the final answer.

    Retries up to 4 times with exponential back-off on NVIDIA overload errors
    so transient free-tier throttling doesn't surface as a user-facing failure.
    """
    model = config.get("configurable", {}).get("model") if config else None
    llm = _make_llm(model=model)
    llm_with_tools = llm.bind_tools(TOOLS)

    messages = state["messages"]
    if not any(isinstance(m, SystemMessage) for m in messages):
        messages = [SystemMessage(content=SYSTEM_PROMPT)] + list(messages)

    for attempt in range(4):
        try:
            response = await llm_with_tools.ainvoke(messages)
            return {"messages": [response]}
        except Exception as exc:
            is_overload = any(kw in str(exc) for kw in ("overloaded", "temporarily", "Service temporarily"))
            if is_overload and attempt < 3:
                wait = 5 * (2 ** attempt)   # 5 s → 10 s → 20 s
                await asyncio.sleep(wait)
                continue
            raise


tool_node = ToolNode(tools=TOOLS)


# ── Graph ───────────────────────────────────────────────────────────────────────

def build_graph():
    graph = StateGraph(AgentState)

    graph.add_node("agent", agent_node)
    graph.add_node("tools", tool_node)

    graph.add_edge(START, "agent")

    # tools_condition: routes to "tools" if last message has tool_calls, else END
    graph.add_conditional_edges("agent", tools_condition)

    # After tools execute, always go back to the agent so it can read the result
    graph.add_edge("tools", "agent")

    return graph.compile()


graph = build_graph()
