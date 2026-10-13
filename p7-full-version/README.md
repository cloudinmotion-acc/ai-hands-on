# P7 - Requirement-to-Design Architect Bot

Five specialist AI agents turn one paragraph of requirements into a full system design document - with a human review gate between every stage. The session survives page refresh. You can edit any stage before the next one runs.

## What it does

```
User writes requirement (one paragraph)
  → Scoping agent      → scope + assumptions + risks
        ↓ [Human: Approve / Edit]
  → Solution agent     → approach + tech stack + NFRs
        ↓ [Human: Approve / Edit]
  → HLD agent          → components + data flow + interfaces
        ↓ [Human: Approve / Edit]
  → LLD agent          → schemas + API contracts + DDL
        ↓ [Human: Approve / Edit]
  → Doc assembler      → final .docx download
```

Every stage streams tokens live. The graph pauses at each interrupt and saves a SQLite checkpoint - if you close the tab and come back, the session is exactly where you left it.

## Concepts demonstrated

| Concept | Where |
|---|---|
| LangGraph stateful graph with `interrupt_after` | `backend/graph/builder.py` |
| Human-in-the-Loop (HITL) approve / edit flow | `backend/main.py` `/resume` endpoint |
| SQLite checkpointing (session survives refresh) | `AsyncSqliteSaver` in `backend/main.py` |
| Regenerate from any stage (ripple-forward) | `backend/main.py` `/regenerate/{stage}` |
| SSE streaming with live token display | `backend/main.py` `_stream_graph()` |
| Context compaction (LLD only gets truncated scope/solution) | `backend/agents/lld.py` |
| Full pipeline trace in-browser | `frontend/components/TraceDrawer.tsx` |
| Checkpoint save/restore events visible in UI | sidebar activity feed |

## Stack

- **Backend:** Python, FastAPI, LangGraph, AsyncSqliteSaver, aiosqlite
- **Agents:** NVIDIA NIM (`nemotron-3-super-120b-a12b`) via LangChain OpenAI adapter
- **Frontend:** Next.js 14, Tailwind CSS, ReactMarkdown + remark-gfm, SSE streaming
- **Storage:** SQLite (checkpoints), outputs/ folder (.docx files)
- **Doc generation:** python-docx

## Setup

```bash
cd p7-full-version/backend
pip install -r requirements.txt
cp .env.example .env       # fill in NVIDIA_API_KEY and AGENT_MODEL
```

**backend/.env**

```
NVIDIA_API_KEY=nvapi-your-key-here
NVIDIA_BASE_URL=https://integrate.api.nvidia.com/v1
AGENT_MODEL=nvidia/nemotron-3-super-120b-a12b
CHECKPOINT_DB=checkpoints.db
```

```bash
cd p7-full-version/frontend
npm install
```

## Run

```bash
# Terminal 1 - backend
cd p7-full-version/backend
uvicorn main:app --port 8000

# Terminal 2 - frontend
cd p7-full-version/frontend
npm run dev      # runs on port 3002
```

Open `http://localhost:3002`.

## API endpoints

| Method | Path | What it does |
|---|---|---|
| `POST` | `/sessions` | Create session, returns `session_id` |
| `GET` | `/sessions/{id}/state` | Full state dump (used on page refresh) |
| `POST` | `/sessions/{id}/start` | SSE: submit requirement, run scoping |
| `POST` | `/sessions/{id}/resume` | SSE: approve or edit current stage, run next |
| `POST` | `/sessions/{id}/regenerate/{stage}` | SSE: clear from stage onwards, re-run |
| `GET` | `/sessions/{id}/download` | Stream the generated .docx |
| `GET` | `/health` | Liveness check |

## SSE events

| Event | When emitted |
|---|---|
| `node_start` | A stage agent just started running |
| `token` | One streamed token from the LLM |
| `stage_complete` | Node finished - contains full content |
| `checkpoint_saved` | SQLite checkpoint written, graph paused |
| `checkpoint_restored` | Checkpoint loaded, graph resuming |
| `awaiting_review` | Graph paused at interrupt - human action needed |
| `session_complete` | All stages done, .docx ready |
| `error` | Graph or agent threw an exception |
| `done` | Stream closed |

## Project structure

```
p7-full-version/
  backend/
    graph/
      state.py          ← ArchitectState TypedDict + Stage type
      nodes.py          ← one async function per stage (calls the agent)
      builder.py        ← StateGraph wired with interrupt_after
    agents/
      base.py           ← get_llm() + safe_format() (avoids {brace} collisions)
      scoping.py        ← scoping agent (requirement → scope)
      solution.py       ← solution agent (scope → architecture)
      hld.py            ← HLD agent (solution → component diagram text)
      lld.py            ← LLD agent (hld → schemas + DDL, context-compacted)
      doc_assembler.py  ← assembles all four outputs into markdown
    doc_gen/
      generator.py      ← markdown → .docx via python-docx
    prompts/            ← one .txt prompt file per agent
    main.py             ← FastAPI + lifespan + _stream_graph + all endpoints
    requirements.txt
    .env.example
  frontend/
    app/
      page.tsx          ← full session UI: sidebar + streaming + trace
      globals.css       ← md-prose styles (tables, code, headings)
    components/
      StageCard.tsx     ← approve / edit panel per stage
      StageProgress.tsx ← left sidebar stage tracker
      EditPanel.tsx     ← textarea + submit for stage edits
      DocumentPreview.tsx ← final doc viewer + download button
      TraceDrawer.tsx   ← full SSE event timeline slide-over
    lib/
      types.ts          ← Stage, SessionState, SSEEvent, TraceEntry types
      api.ts            ← typed fetch wrappers for all 6 endpoints
      session.ts        ← localStorage save/load/clear for thread_id
```

## Test requirement

```
Build a LinkedIn post scheduling assistant that lets content creators write post
drafts, schedule them for optimal engagement times, and get AI-suggested reactions.
It should support multiple social accounts and provide analytics on post performance.
```
