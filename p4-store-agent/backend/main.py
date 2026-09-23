"""
P4 Store Agent — FastAPI backend

Endpoints:
  POST /chat        — streams agent trace as SSE events
  GET  /scenarios   — returns the 5 built-in demo scenarios
  GET  /health      — liveness check
"""

import asyncio
import json
import traceback
from typing import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage

from agent import graph

app = FastAPI(title="P4 Store Agent")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Demo scenarios ──────────────────────────────────────────────────────────────

SCENARIOS = [
    {
        "id": 1,
        "label": "Happy path",
        "description": "2 Blue Shirts, size M → Bangalore",
        "request": "I'd like to order 2 blue classic cotton shirts in size M, delivered to pincode 560001.",
    },
    {
        "id": 2,
        "label": "Bulk discount",
        "description": "5 Black Hoodies, size L → Mumbai",
        "request": "Please order 5 black pullover hoodies in size L, to be shipped to pincode 400001.",
    },
    {
        "id": 3,
        "label": "Out of stock",
        "description": "3 Olive Hoodies, size M → Bangalore",
        "request": "Can I get 3 olive hoodies in size M delivered to 560001?",
    },
    {
        "id": 4,
        "label": "Bad pincode",
        "description": "1 White Polo, size S → invalid pin",
        "request": "Order 1 white polo t-shirt size S and deliver to pincode 999999.",
    },
    {
        "id": 5,
        "label": "Express + bulk",
        "description": "6 Navy Jeans, size M → Delhi (express)",
        "request": "I need 6 navy slim fit jeans in size M, express delivery to 110001.",
    },
]


# ── SSE helpers ─────────────────────────────────────────────────────────────────

def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def _friendly_error(raw: str) -> str:
    if "Service temporarily overloaded" in raw or "overloaded_error" in raw:
        return "NVIDIA API is temporarily overloaded. Wait a moment and retry."
    if "APIConnectionError" in raw or "Connection refused" in raw:
        return "Cannot reach NVIDIA API. Check your connection."
    if "rate_limit" in raw.lower() or "429" in raw:
        return "Rate limit reached. Please wait before retrying."
    return raw.split("\n")[0][:300]


async def _stream_agent(user_request: str, model: str | None = None) -> AsyncIterator[str]:
    """
    Runs the LangGraph agent and yields SSE frames for each step.

    Event types:
      start       — run begins
      thought     — LLM reasoning tokens (streaming)
      tool_call   — which tool + args the agent chose
      observation — result returned by the tool
      answer      — full final answer text (last LLM turn, no tool calls)
      done        — run complete
      error       — unrecoverable failure
    """
    yield _sse("start", {"message": "Agent started"})

    try:
        inputs = {"messages": [HumanMessage(content=user_request)]}
        run_config = {"configurable": {"model": model}} if model else {}
        current_thought: list[str] = []

        async for event in graph.astream_events(inputs, version="v2", config=run_config):
            kind = event["event"]
            name = event.get("name", "")

            if kind == "on_chat_model_stream":
                chunk = event["data"]["chunk"]
                content = chunk.content
                if isinstance(content, list):
                    content = " ".join(
                        c.get("text", "") if isinstance(c, dict) else str(c)
                        for c in content
                    )
                if content:
                    current_thought.append(content)
                    yield _sse("thought", {"token": content})

            elif kind == "on_chat_model_end":
                output = event["data"].get("output")
                tool_calls = getattr(output, "tool_calls", []) if output else []
                if not tool_calls and current_thought:
                    yield _sse("answer", {"text": "".join(current_thought)})
                current_thought = []

            elif kind == "on_tool_start":
                current_thought = []
                yield _sse("tool_call", {
                    "tool":  name,
                    "input": event["data"].get("input", {}),
                })

            elif kind == "on_tool_end":
                output = event["data"].get("output", "")
                if hasattr(output, "content"):
                    try:
                        output = json.loads(output.content)
                    except Exception:
                        output = {"raw": str(output.content)}
                elif isinstance(output, str):
                    try:
                        output = json.loads(output)
                    except json.JSONDecodeError:
                        pass
                yield _sse("observation", {
                    "tool":   name,
                    "result": output,
                })

        yield _sse("done", {"success": True})

    except Exception as exc:
        yield _sse("error", {"message": _friendly_error(str(exc))})
        yield _sse("done", {"success": False})


# ── Routes ───────────────────────────────────────────────────────────────────────

@app.post("/chat")
async def chat(request: Request):
    body = await request.json()
    user_request = (body.get("request") or "").strip()
    model = body.get("model") or None
    if not user_request:
        return JSONResponse({"detail": "request field is required"}, status_code=400)

    return StreamingResponse(
        _stream_agent(user_request, model=model),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/scenarios")
def get_scenarios():
    return {"scenarios": SCENARIOS}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.exception_handler(Exception)
async def global_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"detail": str(exc)},
        headers={"Access-Control-Allow-Origin": "*"},
    )
