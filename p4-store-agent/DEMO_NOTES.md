# P4 — Store Agent · Demo Notes

---

## The Problem

A customer asks: "I want 3 blue shirts in size M, delivered to 560001 — what's the total including delivery?"

A simple chatbot can't answer this. It's not one question — it's three sequential operations: check whether 3 blue shirts (size M) are in stock, calculate the price with applicable discounts, and look up the delivery timeline for that pincode. Each step depends on the result of the previous one. If stock is unavailable, you don't need to calculate price.

This kind of task — multi-step, conditional, tool-dependent — is where single-turn chatbots break. You need an agent that can plan, call tools in sequence, and decide when to stop.

---

## The Solution

A LangGraph ReAct agent with three tools.

**ReAct** (Reason + Act) is the pattern: the LLM reasons about what it needs to do next, decides which tool to call, calls it, reads the result, reasons again, and repeats until it has enough information to answer. It's an autonomous loop, not a single call.

**LangGraph** is the framework that manages this loop as a state machine. The state is the full conversation history. The graph has two nodes — `agent` (LLM) and `tools` (tool execution) — and a conditional edge that routes: if the LLM's last message contains tool calls, go to `tools`; if it's plain text, we're done.

**Three tools:**
- `check_stock(product, color, size, quantity)` → is it available?
- `price_order(sku, quantity, unit_price, first_order)` → what's the cost after discounts?
- `delivery_eta(pincode, shipping_type)` → when does it arrive?

Every step is streamed to the UI — the user sees the agent thinking, calling tools, reading results, and forming the answer in real time.

---

## What Makes This Different

**vs. simple tool-calling (single LLM call with tools):**
A single LLM call with tools can call one tool and return. LangGraph gives you a stateful loop — the agent reads the tool result, reasons about it, and decides whether to call another tool. The flow is: agent → tools → agent → tools → agent → done. That loop is what enables multi-step conditional logic.

**vs. LangChain AgentExecutor (the old way):**
AgentExecutor is a black box — you can't control routing, add human-in-the-loop steps, or inspect state mid-execution. LangGraph's `StateGraph` makes the execution graph explicit. You can add nodes, change routing, inspect state at any point. It's the composable version.

**vs. other portfolio projects:**
Most agent demos show a single tool call. This shows a three-tool sequential flow with an explicit stopping condition (out of stock → stop immediately, don't calculate price). That conditional halt demonstrates that the agent understands business logic, not just tool syntax.

---

## Demo Tour

### Before you start
- [ ] Backend: `uvicorn main:app --port 8001` from `p4-store-agent/backend/`
- [ ] Frontend: `npm run dev` from `p4-store-agent/frontend/`

---

### Step 1 — Open the app
**Open:** `http://localhost:3000`

**Say:**
> "This is the Store Agent. Unlike a simple chatbot, this agent can perform multi-step operations — it has tools it can call, and it decides in real time which tools to use and in what order. Watch what happens when I send a complex request."

---

### Step 2 — Send a complete order query
**Do:** Type: `"I want 3 blue shirts in size M delivered to 560001. What's the total?"`

**Say:**
> "I'm asking something that requires three separate lookups. Watch the trace on the right — you'll see the agent's thinking unfold step by step."

**As the trace appears, narrate:**
> - When `tool_call: check_stock` appears: "First it's checking stock — do we have 3 blue shirts in size M?"
> - When `tool_result: check_stock` appears: "Stock confirmed — shows SKU, unit price, available quantity."
> - When `tool_call: price_order` appears: "Now it's calculating price. Notice it passed the exact SKU and unit price from the stock check — it's chaining tool outputs."
> - When `tool_call: delivery_eta` appears: "And now delivery time for that pincode."
> - When `final_answer` appears: "The agent has all three pieces of information and synthesises the final answer — stock confirmed, final total with any discounts, delivery date."

---

### Step 3 — Show the early stop on out-of-stock
**Do:** Type: `"I want 50 navy bomber jackets in size XL delivered to 110001."`

**Say:**
> "Now I'm asking for 50 units — more than we have in stock. Watch what happens."

**As trace appears:**
> "It called check_stock, got back `in_stock: false`. Now watch — it stops. It does NOT call price_order or delivery_eta. There's no point calculating a price for something we can't fulfil. The agent understood the business logic: if stock fails, abort the sequence."

---

### Step 4 — (If time) Try a first-order discount
**Do:** Type: `"First time customer here. 2 white polo shirts size L to 400001."`

**Say:**
> "First-order discount. The `price_order` tool takes a `first_order` parameter — the agent reads that from my message and passes it correctly. Discount applies automatically."

---

## Code Walkthrough

### `agent.py` — LangGraph graph definition

**What it does:** Defines the `AgentState`, creates the LLM with tools bound to it, builds the LangGraph `StateGraph` with two nodes and conditional routing.

**Key function: `agent_node(state, config)`**
```python
async def agent_node(state: AgentState, config: RunnableConfig) -> dict:
    llm_with_tools = llm.bind_tools(TOOLS)
    messages = state["messages"]
    # inject system prompt if not already present
    response = await llm_with_tools.ainvoke(messages)
    return {"messages": [response]}
```
Plain English: Every time the graph routes back to the agent node, it takes the full message history (including all tool call results so far), passes it to the LLM, and gets back either another tool call or a final text answer. The LLM has full memory of everything that happened so it can chain tool outputs.

The 4-attempt exponential backoff (5s → 10s → 20s) is inside this function — NVIDIA NIM returns 429 under free-tier load. Without backoff, a single rate-limit error kills the whole agent run.

**Key function: `build_graph()`**
```python
graph.add_conditional_edges("agent", tools_condition)
graph.add_edge("tools", "agent")
```
`tools_condition` is a LangGraph built-in: if the last AIMessage has `tool_calls`, route to `"tools"`. Otherwise route to `END`. After tools execute, always route back to `"agent"` so the LLM can read the result. This is the ReAct loop in two lines.

---

### `tools.py` — three tools with JSON data files

**What it does:** Defines `check_stock`, `price_order`, and `delivery_eta` as LangChain tools. Each reads a JSON data file (inventory, discounts, shipping zones) and returns a structured dict. Errors are returned as `{"error": "..."}` — not raised as exceptions — so the agent can reason about the failure.

**Key function: `check_stock(product_name, color, size, quantity)`**

The flexible name matching is worth noting:
```python
NAME_MAP = {
    "shirt": "classic cotton shirt",
    "polo":  "polo t-shirt",
    "jeans": "slim fit jeans",
    ...
}
```
Users say "shirt", the JSON has "classic cotton shirt". Without this mapping, the tool returns no match. This is the same problem as RAG — bridge the gap between how users talk and how data is stored.

**Key function: `price_order(sku, quantity, unit_price, first_order)`**

Finds the best applicable discount from `discounts.json` by scanning all rules:
- Bulk discount: quantity >= min_quantity
- SKU-specific discount: product is in the discount's SKU list
- First-order discount: `first_order=True`

Takes the highest discount percent. Returns both the base total and the discounted final total — the agent presents both in its answer.

**Key function: `delivery_eta(pincode, shipping_type)`**

Zones the pincode (metro/tier1/tier2/remote) and looks up days + cost for standard or express. Returns `estimated_delivery` as a formatted date string (`"15 Nov 2026"`) — the agent uses this directly in the final answer, no further formatting needed.

---

### `main.py` — FastAPI + SSE streaming

**What it does:** Exposes `POST /chat` which runs the LangGraph graph and streams events as SSE. For each graph update, it inspects the message type and emits the appropriate event.

**Key pattern: streaming graph updates**
```python
async for event in GRAPH.astream(initial_state, stream_mode="updates"):
    for node_name, node_output in event.items():
        for msg in node_output["messages"]:
            if isinstance(msg, AIMessage) and msg.tool_calls:
                yield _sse({"type": "tool_call", ...})
            elif isinstance(msg, ToolMessage):
                yield _sse({"type": "tool_result", ...})
```
`stream_mode="updates"` makes LangGraph emit one event per node update — so you get tool calls as they happen, not batched at the end. The frontend renders each event as it arrives, giving the live trace effect.

---

## New Concepts to Stress

### ReAct Pattern (Reason + Act)
The core agentic loop: the LLM reasons about what information it needs, acts (calls a tool), reads the result, and reasons again. Introduced in a 2022 Google Research paper ("ReAct: Synergizing Reasoning and Acting in Language Models"). Now the standard pattern for any LLM agent that needs to do multi-step work. LangGraph implements it as a graph with conditional routing.

### LangGraph StateGraph
LangGraph models agent execution as a directed graph of nodes (functions) connected by edges (routing rules). State is a TypedDict that flows through the graph — each node receives the state, does work, and returns updates. The `add_messages` reducer automatically merges message lists so you don't manually manage conversation history. The key advantage over LangChain's `AgentExecutor`: full control over routing, visibility into state at any point, easy to add nodes (human approval, logging, retry).

### `tools_condition`
A LangGraph built-in routing function. It inspects the last message in state — if it has `tool_calls`, route to the tools node; otherwise route to `END`. Two lines replace what would otherwise be 20 lines of if/else routing logic. Important to understand: it's not magic — you can write your own routing function that does more complex logic (e.g. route to different tool nodes based on which tool was called).

### SSE (Server-Sent Events)
A one-directional HTTP streaming protocol: the server keeps the connection open and pushes events as they happen. Each event is `data: {...}\n\n`. The browser's `EventSource` API reads these. Used here because tool calls happen on the server over seconds — SSE lets the UI show progress in real time without polling. WebSockets would work too but are bidirectional — SSE is simpler when you only need server→client streaming.

---

## Conclusion

P4 demonstrates the jump from single-turn chatbots to stateful agents. LangGraph's explicit state machine makes the agent's reasoning inspectable and controllable — you can see every tool call, every result, every decision. The streaming trace is not just a UI feature; it's a debugging interface.

**Key takeaway for the room:** An agent is not a smarter chatbot — it's a planning system. The intelligence is in the loop (reason → act → observe → reason), not in any single LLM call. Understanding the loop is what separates building agents from prompting models.
