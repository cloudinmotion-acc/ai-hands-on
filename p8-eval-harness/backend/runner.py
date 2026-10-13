"""
P7 API runner: calls the P7 REST API to run a full design session with auto-approval.

SSE event stream structure per POST:
  - stage_complete → outputs[stage] = content
  - awaiting_review → graph paused, human action needed
  - session_complete → all stages done
  - error → graph threw an exception
  - done → stream closed

Each POST /start or /resume opens a new SSE stream that closes when the graph
pauses at an interrupt or completes. We call /resume until session_complete.
"""

import asyncio
import json
import logging
import time
from typing import AsyncGenerator

import httpx

logger = logging.getLogger("p8.runner")

STAGES = ["scoping", "solution", "hld", "lld"]


async def _read_sse(response: httpx.Response) -> AsyncGenerator[dict, None]:
    """Parse SSE events from an httpx async streaming response."""
    async for line in response.aiter_lines():
        line = line.strip()
        if line.startswith("data: "):
            try:
                yield json.loads(line[6:])
            except json.JSONDecodeError:
                pass


async def create_session(*, p7_url: str) -> str:
    """POST /sessions on the P7 backend and return the session_id."""
    async with httpx.AsyncClient(verify=False, timeout=30) as client:
        resp = await client.post(f"{p7_url}/sessions")
        resp.raise_for_status()
        return resp.json()["session_id"]


async def run_scenario(
    *,
    requirement: str,
    p7_url: str,
    session_id: str,
    edit_at: dict | None = None,
    timeout: int = 300,
) -> dict:
    """
    Run one full design session via the P7 REST API with automatic approval.

    Args:
        requirement: the requirement text to submit
        p7_url: base URL of the P7 backend (e.g. "http://localhost:8000")
        session_id: P7 session ID (from POST /sessions)
        edit_at: optional dict {"stage": "scoping", "inject": "..."} to inject
                 a constraint into the named stage's output before approving
        timeout: per-request timeout in seconds

    Returns:
        {
            "stages_completed": list[str],
            "stage_order": list[str],
            "outputs": dict[str, str],
            "duration_s": float,
            "error": str | None
        }
    """
    t0 = time.monotonic()
    stages_completed: list[str] = []
    stage_order: list[str] = []
    outputs: dict[str, str] = {}

    async def _stream_to_interrupt(client: httpx.AsyncClient, method: str, url: str, body: dict):
        """
        Send a POST and read SSE events until awaiting_review or session_complete.
        Returns: ("awaiting", stage_name) | ("complete", None) | ("error", message)
        """
        nonlocal stages_completed, stage_order, outputs

        try:
            async with client.stream(method, url, json=body) as response:
                if response.status_code >= 400:
                    err_body = await response.aread()
                    try:
                        detail = json.loads(err_body).get("detail", err_body.decode())
                    except Exception:
                        detail = err_body.decode()
                    return ("error", f"HTTP {response.status_code}: {detail}")

                async for event in _read_sse(response):
                    ev_type = event.get("type")

                    if ev_type == "stage_complete":
                        stage = event.get("stage", "")
                        content = event.get("content", "")
                        if stage and stage not in stages_completed:
                            stages_completed.append(stage)
                            stage_order.append(stage)
                        if stage:
                            outputs[stage] = content

                    elif ev_type == "awaiting_review":
                        return ("awaiting", event.get("stage", ""))

                    elif ev_type == "session_complete":
                        return ("complete", None)

                    elif ev_type == "error":
                        return ("error", event.get("message", "Unknown graph error"))

        except httpx.TimeoutException:
            return ("error", f"Timeout after {timeout}s")
        except Exception as exc:
            return ("error", str(exc))

        return ("done", None)

    try:
        async with httpx.AsyncClient(verify=False, timeout=timeout) as client:
            # Stream 1: start the session (runs scoping)
            logger.info(f"[{session_id[:8]}] Starting session")
            status, current_stage = await _stream_to_interrupt(
                client, "POST",
                f"{p7_url}/sessions/{session_id}/start",
                {"requirement": requirement},
            )

            # Streams 2-5: resume until session_complete
            stream_num = 0
            while status == "awaiting" and stream_num < 5:
                stream_num += 1

                # Decide: approve or inject edit?
                last_stage = stage_order[-1] if stage_order else None
                if edit_at and edit_at.get("stage") == last_stage:
                    original = outputs.get(last_stage, "")
                    injected = original + edit_at["inject"]
                    body = {"action": "edit", "content": injected}
                    logger.info(f"[{session_id[:8]}] Injecting edit at stage={last_stage}")
                else:
                    body = {"action": "approve"}
                    logger.info(f"[{session_id[:8]}] Approving stage={last_stage}")

                status, current_stage = await _stream_to_interrupt(
                    client, "POST",
                    f"{p7_url}/sessions/{session_id}/resume",
                    body,
                )

            if status == "error":
                logger.error(f"[{session_id[:8]}] Error: {current_stage}")
                return {
                    "stages_completed": stages_completed,
                    "stage_order": stage_order,
                    "outputs": outputs,
                    "duration_s": round(time.monotonic() - t0, 1),
                    "error": current_stage,
                }

    except Exception as exc:
        logger.error(f"[{session_id[:8]}] Unexpected error: {exc}", exc_info=True)
        return {
            "stages_completed": stages_completed,
            "stage_order": stage_order,
            "outputs": outputs,
            "duration_s": round(time.monotonic() - t0, 1),
            "error": str(exc),
        }

    return {
        "stages_completed": stages_completed,
        "stage_order": stage_order,
        "outputs": outputs,
        "duration_s": round(time.monotonic() - t0, 1),
        "error": None,
    }
