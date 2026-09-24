# Project: AI Agentic Training Portfolio (P1–P8)

Bharath Aaleti — FDE / AI Engineer @ Accenture.
Goal: interview-ready + demo-ready AI engineering portfolio.

## What's built

| Phase | Name | Status |
|---|---|---|
| P1 | Invoice AI (structured extraction + self-verification) | Done |
| P2 | RAG Assistant (pgvector + FastAPI + Next.js frontend) | Done |
| P3 | RAG Quality Gate (RAGAS eval + Streamlit dashboard) | Done |
| P4–P8 | TBD | Planned |

## Stack

- **Backend:** Python, FastAPI, LangChain, RAGAS 0.4.3
- **Models:** NVIDIA NIM API (`nemotron-3-super-120b`, `gpt-oss-20b` judge, `nemotron-3-embed-1b`)
- **DB:** pgvector (Docker), ChromaDB fallback
- **Env:** Windows 11, `.venv` at repo root, Accenture corporate proxy (`verify=False` in dev)

## Running locally

```bash
# P2 backend
uvicorn main:app --port 8000       # from p2-rag-assistant/backend/

# P2 frontend
npm run dev                        # from p2-rag-assistant/frontend/

# P3 eval
python run_eval.py                 # from p3-rag-eval/

# P3 dashboard
```

## Key environment notes

- `.env` files live inside each phase folder — never commit them
- `NVIDIA_API_KEY` required for P2 and P3
- Corporate proxy intercepts HTTPS → `httpx.Client(verify=False)` in dev; prod fix is adding Accenture CA bundle
- `langchain_community.chat_models.vertexai` is missing in langchain-community 0.3+ — a stub is injected at the top of `run_eval.py` before any RAGAS import

## RAGAS 0.4.3 quirks (hard-won)

- `evaluate()` only accepts old `Metric` subclasses (private names: `_LLMContextPrecisionWithReference`, `_LLMContextRecall`, `_Faithfulness`, `_ResponseRelevancy`). New `BaseMetric` classes from `ragas.metrics.collections` are NOT compatible.
- `_ResponseRelevancy` calls `embed_query()` / `embed_documents()` synchronously from inside RAGAS's async loop — use a sync `OpenAI` client for those methods, not `asyncio.run()` (nested loop deadlock).
- `llm_factory(model, client=AsyncOpenAI(...), temperature=1)` — temperature=1 is required for gpt-oss-20b.

## Design conventions

### Impeccable skill — ALWAYS use for any UI work

The `impeccable` skill is configured at `.agents/skills/impeccable/SKILL.md`.
Run its context script before any UI edit:

```bash
.agents/skills/impeccable/scripts/impeccable.cmd context --target <file>
```

Then load `reference/craft-floor.md` before writing code. Never skip this for UI tasks —
the skill sets the quality floor, bans, and design direction process.

