"""
P7 FastAPI backend  -  Requirement-to-Design Architect Bot.

Endpoints:
  POST /sessions                         → create session, return session_id
  GET  /sessions/{id}/state              → get full state (for page refresh)
  POST /sessions/{id}/start              → SSE: run first stage (scoping)
  POST /sessions/{id}/resume             → SSE: approve or edit current stage, run next
  POST /sessions/{id}/regenerate/{stage} → SSE: clear from stage onwards, re-run
  GET  /sessions/{id}/download           → stream .docx file
  GET  /health                           → liveness check
"""

import json
import logging
import os
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator, Literal

import aiosqlite
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from graph.builder import build_graph, STAGE_NODES, STAGE_ORDER
from doc_gen.generator import generate as generate_docx

# Maps stage name (current_stage value) → the key used in ArchitectState
# "scoping" → "scope", all others match their stage name
STAGE_STATE_KEY: dict[str, str] = {
    "scoping":  "scope",
    "solution": "solution",
    "hld":      "hld",
    "lld":      "lld",
}

load_dotenv()

# ── Logging ───────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)-5s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("p7")

# ── Globals ───────────────────────────────────────────────────────────────────

_db_conn: aiosqlite.Connection | None = None
graph = None

SSE_HEADERS = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}

STAGE_LABELS = {
    "scoping": "Scoping",
    "solution": "Solution",
    "hld": "High-Level Design",
    "lld": "Low-Level Design",
    "doc": "Document",
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _db_conn, graph

    env_path = Path(__file__).parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)

    db_path = os.environ.get("CHECKPOINT_DB", "checkpoints.db")
    logger.info(f"Opening SQLite checkpoint DB: {db_path}")
    _db_conn = await aiosqlite.connect(db_path)
    checkpointer = AsyncSqliteSaver(_db_conn)
    await checkpointer.setup()
    logger.info("Checkpointer ready")

    graph = build_graph(checkpointer)
    Path("outputs").mkdir(exist_ok=True)
    logger.info("Graph compiled. Server ready.")

    yield

    if _db_conn is not None:
        await _db_conn.close()


app = FastAPI(title="P7 Architect Bot", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _sse(data: dict) -> str:
    return f"data: {json.dumps(data)}\n\n"


def _config(session_id: str) -> dict:
    return {"configurable": {"thread_id": session_id}}


async def _stream_graph(
    session_id: str,
    initial_input: dict | None = None,
    is_resume: bool = False,
    resume_stage: str | None = None,
) -> AsyncGenerator[str, None]:
    """
    Run or resume the graph and yield SSE events.

    When initial_input is provided the graph starts fresh from that state.
    When initial_input is None the graph resumes from the last checkpoint.
    When is_resume=True, emits a checkpoint_restored event first.
    """
    config = _config(session_id)

    # Announce checkpoint restore at the start of any resume
    if is_resume and resume_stage:
        label = STAGE_LABELS.get(resume_stage, resume_stage)
        logger.info(f"[{session_id[:8]}] Checkpoint restored  -  resuming from {resume_stage}")
        yield _sse({"type": "checkpoint_restored", "stage": resume_stage, "label": label})

    token_count = 0

    try:
        async for event in graph.astream_events(
            initial_input, config, version="v2"
        ):
            kind = event["event"]
            node_name = event.get("name", "")

            # ── Node started ──────────────────────────────────────────────
            if kind == "on_chain_start" and node_name in STAGE_NODES:
                label = STAGE_LABELS.get(node_name, node_name)
                logger.info(f"[{session_id[:8]}] ▶ Node start: {node_name}")
                token_count = 0
                yield _sse({"type": "node_start", "stage": node_name, "label": label})

            # ── Stream LLM tokens ─────────────────────────────────────────
            elif kind == "on_chat_model_stream":
                chunk = event["data"].get("chunk")
                if chunk and hasattr(chunk, "content") and chunk.content:
                    token_count += 1
                    yield _sse({"type": "token", "content": chunk.content})

            # Node finished
            elif kind == "on_chain_end" and node_name in STAGE_NODES:
                # Use node return value directly  -  aget_state mid-loop reads stale checkpoint.
                output = event.get("data", {}).get("output") or {}
                state_key = STAGE_STATE_KEY.get(node_name, "")
                stage_data = output.get(state_key) if state_key else None
                content = (
                    stage_data.get("content", "")
                    if isinstance(stage_data, dict)
                    else ""
                )
                # Fallback: some LG versions wrap output differently
                if not content:
                    try:
                        fb = await graph.aget_state(config)
                        fb_data = fb.values.get(state_key) if state_key else None
                        content = (
                            fb_data.get("content", "")
                            if isinstance(fb_data, dict)
                            else ""
                        )
                    except Exception:
                        pass

                logger.info(
                    f"[{session_id[:8]}] Node end: {node_name} "
                    f"({len(content)} chars, {token_count} tokens)"
                )
                yield _sse(
                    {
                        "type": "stage_complete",
                        "stage": node_name,
                        "content": content,
                        "next_nodes": [],
                    }
                )

    except Exception as exc:
        logger.error(f"[{session_id[:8]}] Graph error: {exc}", exc_info=True)
        yield _sse({"type": "error", "message": str(exc)})
        yield _sse({"type": "done"})
        return

    # ── After stream ends: interrupted or complete ────────────────────────
    state = await graph.aget_state(config)
    next_nodes = list(state.next) if state else []
    current = state.values.get("current_stage") if state else None
    logger.info(
        f"[{session_id[:8]}] Stream ended  -  current_stage={current}, next={next_nodes}"
    )

    if not next_nodes:
        # Graph ran to completion  -  generate .docx if needed
        doc_text: str | None = state.values.get("doc_text")
        if doc_text and not state.values.get("docx_path"):
            logger.info(f"[{session_id[:8]}] Generating .docx")
            docx_path = generate_docx(session_id, doc_text)
            await graph.aupdate_state(
                config,
                {"docx_path": docx_path, "current_stage": "complete"},
            )
        logger.info(f"[{session_id[:8]}] Session complete")
        yield _sse({"type": "session_complete"})
    else:
        # Graph paused at an interrupt  -  human review needed
        label = STAGE_LABELS.get(current or "", current or "")
        logger.info(
            f"[{session_id[:8]}] ⏸ Interrupt at {current}  -  checkpoint saved, next={next_nodes}"
        )
        yield _sse({"type": "checkpoint_saved", "stage": current, "label": label})
        yield _sse({"type": "awaiting_review", "stage": current})

    yield _sse({"type": "done"})


# ── Request models ────────────────────────────────────────────────────────────

class StartRequest(BaseModel):
    requirement: str


class ResumeRequest(BaseModel):
    action: Literal["approve", "edit"]
    content: str | None = None  # required only when action == "edit"


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.post("/sessions")
async def create_session() -> dict:
    sid = str(uuid.uuid4())
    logger.info(f"[{sid[:8]}] New session created")
    return {"session_id": sid}


@app.get("/sessions/{session_id}/state")
async def get_state(session_id: str) -> dict:
    try:
        state = await graph.aget_state(_config(session_id))
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    if not state or not state.values:
        raise HTTPException(status_code=404, detail="Session not found")

    awaiting = bool(state.next)
    logger.info(
        f"[{session_id[:8]}] GET state  -  stage={state.values.get('current_stage')}, "
        f"awaiting={awaiting}, next={list(state.next)}"
    )

    return {
        "session_id": session_id,
        "current_stage": state.values.get("current_stage"),
        "requirement": state.values.get("requirement", ""),
        "scope": state.values.get("scope"),
        "solution": state.values.get("solution"),
        "hld": state.values.get("hld"),
        "lld": state.values.get("lld"),
        "doc_text": state.values.get("doc_text"),
        "docx_path": state.values.get("docx_path"),
        "awaiting_review": awaiting,
    }


@app.post("/sessions/{session_id}/start")
async def start_session(session_id: str, req: StartRequest) -> StreamingResponse:
    logger.info(f"[{session_id[:8]}] START  -  requirement: {req.requirement[:80]}...")
    initial: dict = {
        "requirement": req.requirement,
        "scope": None,
        "solution": None,
        "hld": None,
        "lld": None,
        "doc_text": None,
        "docx_path": None,
        "current_stage": "scoping",
    }
    return StreamingResponse(
        _stream_graph(session_id, initial),
        media_type="text/event-stream",
        headers=SSE_HEADERS,
    )


@app.post("/sessions/{session_id}/resume")
async def resume_session(session_id: str, req: ResumeRequest) -> StreamingResponse:
    config = _config(session_id)

    try:
        state = await graph.aget_state(config)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    if not state or not state.values:
        raise HTTPException(status_code=404, detail="Session not found")

    current_stage: str | None = state.values.get("current_stage")
    next_nodes = list(state.next)

    logger.info(
        f"[{session_id[:8]}] RESUME  -  action={req.action}, "
        f"current_stage={current_stage}, state.next={next_nodes}"
    )

    if not current_stage or not next_nodes:
        logger.warning(
            f"[{session_id[:8]}] RESUME rejected  -  state.next is empty. "
            f"current_stage={current_stage}. Graph may not be paused at an interrupt."
        )
        raise HTTPException(
            status_code=400,
            detail=(
                f"No stage is currently awaiting review "
                f"(current_stage={current_stage}, next={next_nodes}). "
                "The graph is not paused at an interrupt."
            ),
        )

    # Map stage name ("scoping") to actual state key ("scope")
    state_key = STAGE_STATE_KEY.get(current_stage, current_stage)
    current_result: dict | None = state.values.get(state_key)
    if current_result is None:
        raise HTTPException(
            status_code=400,
            detail=f"Stage '{current_stage}' has no content (state_key='{state_key}')",
        )

    if req.action == "approve":
        updated = {**current_result, "approved": True}
        logger.info(f"[{session_id[:8]}] Approving {current_stage}")
    else:
        if not req.content:
            raise HTTPException(status_code=422, detail="'content' is required for edit action")
        updated = {"content": req.content, "approved": True, "edited": True}
        logger.info(f"[{session_id[:8]}] Editing {current_stage} ({len(req.content)} chars)")

    await graph.aupdate_state(config, {state_key: updated})

    return StreamingResponse(
        _stream_graph(session_id, None, is_resume=True, resume_stage=current_stage),
        media_type="text/event-stream",
        headers=SSE_HEADERS,
    )


@app.post("/sessions/{session_id}/regenerate/{from_stage}")
async def regenerate_from(session_id: str, from_stage: str) -> StreamingResponse:
    """Clear from_stage and all downstream stages, then re-run from there."""
    if from_stage not in STAGE_ORDER:
        raise HTTPException(status_code=400, detail=f"Unknown stage: '{from_stage}'")

    config = _config(session_id)

    try:
        state = await graph.aget_state(config)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    if not state or not state.values:
        raise HTTPException(status_code=404, detail="Session not found")

    idx = STAGE_ORDER.index(from_stage)
    logger.info(f"[{session_id[:8]}] REGENERATE from {from_stage} (idx={idx})")

    # Build the state patch: clear everything from from_stage onwards
    clear_update: dict = {"current_stage": from_stage, "doc_text": None, "docx_path": None}
    for stage in STAGE_ORDER[idx:]:
        if stage != "doc":
            clear_update[stage] = None

    if idx == 0:
        # Regenerating from the very first stage  -  restart the graph with fresh initial state
        initial = {**state.values, **clear_update}
        return StreamingResponse(
            _stream_graph(session_id, initial),
            media_type="text/event-stream",
            headers=SSE_HEADERS,
        )
    else:
        # Update state as if the previous stage just finished, so the graph
        # will continue from from_stage on the next run.
        prev_stage = STAGE_ORDER[idx - 1]
        logger.info(f"[{session_id[:8]}] Winding back to after {prev_stage}")
        await graph.aupdate_state(config, clear_update, as_node=prev_stage)
        return StreamingResponse(
            _stream_graph(session_id, None),
            media_type="text/event-stream",
            headers=SSE_HEADERS,
        )


@app.get("/sessions/{session_id}/download")
async def download_docx(session_id: str) -> FileResponse:
    config = _config(session_id)

    try:
        state = await graph.aget_state(config)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    docx_path: str | None = state.values.get("docx_path") if state else None
    if not docx_path or not Path(docx_path).exists():
        raise HTTPException(status_code=404, detail="Document not ready  -  complete all stages first")

    return FileResponse(
        path=docx_path,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=f"design_{session_id[:8]}.docx",
    )


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
