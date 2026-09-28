"""
P6 FastAPI server — hardened wrapper around P5.

Flow per request:
  1. Input guards  (injection → PII → topic)
  2. P5 agent      (via HTTP SSE to P5 backend)
  3. Output guards (hallucination + tone)
  4. Stream result to frontend

SSE events emitted:
  guard_info    — when a guard rewrites input or output (logged, not blocking)
  guard_blocked — when injection or topic guard fires
  start / tool_call / tool_result — forwarded directly from P5
  final_answer  — may be the rewritten version from output guard
  done
"""

import json
import os
from pathlib import Path

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from guards import input_guard, output_guard
from tracing import langsmith_tracer

load_dotenv(Path(__file__).parent / ".env")
langsmith_tracer.configure()

P5_BASE_URL = os.environ.get("P5_BASE_URL", "http://localhost:8000")

app = FastAPI(title="P6 Hardened Product Search")

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


async def _stream(query: str):
    with langsmith_tracer.request_trace(query) as meta:

        # ── Step 1: Input guards ──────────────────────────────────────
        input_result = input_guard.check(query)
        meta["input_guard_action"] = input_result.action
        meta["input_guard_reason"] = input_result.reason

        if input_result.action == "block":
            yield _sse({
                "type": "guard_blocked",
                "guard": input_result.guard_name,
                "reason": input_result.reason,
            })
            yield _sse({"type": "done"})
            return

        if input_result.action == "rewrite":
            yield _sse({
                "type": "guard_info",
                "guard": input_result.guard_name,
                "action": "rewrite",
                "reason": input_result.reason,
            })

        query_for_p5 = input_result.modified_text or query

        # ── Step 2: Stream P5, collect final_answer ───────────────────
        tool_result_event = None
        final_answer = None

        try:
            async with httpx.AsyncClient(verify=False, timeout=120) as client:
                async with client.stream(
                    "POST",
                    f"{P5_BASE_URL}/search",
                    json={"query": query_for_p5},
                    headers={"Accept": "text/event-stream"},
                ) as response:
                    async for line in response.aiter_lines():
                        if not line.startswith("data:"):
                            continue

                        event = json.loads(line[5:].strip())
                        event_type = event.get("type")

                        if event_type in ("start", "tool_call"):
                            yield _sse(event)  # forward immediately

                        elif event_type == "tool_result":
                            tool_result_event = event
                            yield _sse(event)  # forward immediately

                        elif event_type == "final_answer":
                            final_answer = event.get("content", "")
                            # Don't yield yet — output guard runs first

                        elif event_type == "error":
                            yield _sse(event)
                            yield _sse({"type": "done"})
                            return

                        # "done" from P5 is swallowed here;
                        # we emit our own done after output guard

        except httpx.ConnectError:
            yield _sse({
                "type": "error",
                "message": f"Cannot reach P5 at {P5_BASE_URL}. Is it running?",
            })
            yield _sse({"type": "done"})
            return

        # ── Step 3: Output guard ──────────────────────────────────────
        if final_answer:
            out_result = output_guard.check(final_answer, tool_result_event)
            meta["output_guard_action"] = out_result.action
            meta["output_guard_reason"] = out_result.reason

            if out_result.action == "rewrite":
                yield _sse({
                    "type": "guard_info",
                    "guard": "output_guard",
                    "action": "rewrite",
                    "reason": out_result.reason,
                })
                final_answer = out_result.modified_text

            yield _sse({"type": "final_answer", "content": final_answer})

        yield _sse({"type": "done"})


@app.post("/search")
async def search(req: SearchRequest):
    return StreamingResponse(
        _stream(req.query),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/health")
async def health():
    return {"status": "ok", "p5_url": P5_BASE_URL}
