"""
P5 FastAPI server — SSE streaming endpoint for the LangGraph shopping agent.

Endpoints:
    POST /search        → JSON body: { "query": str }
                          SSE stream: agent trace events + final answer
    GET  /health        → { "status": "ok" }
"""

import asyncio
import json
import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from pydantic import BaseModel

from agent import GRAPH

load_dotenv(Path(__file__).parent / ".env")

app = FastAPI(title="P5 Product Search")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class SearchRequest(BaseModel):
    query: str


def _sse(data: dict) -> str:
    return f"data: {json.dumps(data)}\n\n"


async def _stream_agent(query: str):
    """Run the LangGraph agent and stream events as SSE."""
    initial_state = {"messages": [HumanMessage(content=query)]}

    yield _sse({"type": "start", "query": query})

    try:
        async for event in GRAPH.astream(initial_state, stream_mode="updates"):
            for node_name, node_output in event.items():
                messages = node_output.get("messages", [])
                for msg in messages:
                    if isinstance(msg, AIMessage):
                        if msg.tool_calls:
                            for tc in msg.tool_calls:
                                yield _sse({
                                    "type": "tool_call",
                                    "tool": tc["name"],
                                    "args": tc["args"],
                                })
                        elif msg.content:
                            yield _sse({"type": "final_answer", "content": msg.content})

                    elif isinstance(msg, ToolMessage):
                        # Parse the JSON result for a nicer trace
                        try:
                            parsed = json.loads(msg.content)
                            yield _sse({
                                "type": "tool_result",
                                "tool": msg.name,
                                "decomposed": parsed.get("decomposed"),
                                "result_count": len(parsed.get("results", [])),
                                "top_results": parsed.get("results", []),
                            })
                        except Exception:
                            yield _sse({
                                "type": "tool_result",
                                "tool": msg.name,
                                "raw": msg.content[:500],
                            })

        yield _sse({"type": "done"})

    except Exception as exc:
        yield _sse({"type": "error", "message": str(exc)})


@app.post("/search")
async def search(req: SearchRequest):
    return StreamingResponse(
        _stream_agent(req.query),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/health")
async def health():
    return {"status": "ok"}
