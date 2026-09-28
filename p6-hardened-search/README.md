# P6 — Hardened Product Search

Guardrail wrapper around P5. Every request passes through input guards before reaching the model and output guards before reaching the user. All decisions are traced in LangSmith.

## What it does

```
User query
  → Input Guards: injection detector → PII scrubber → topic filter
  → P5 Retail Bot (unchanged)
  → Output Guards: hallucination check + tone check
  → Safe reply (or honest refusal)

Everything traced end-to-end in LangSmith
```

## Guards

| Guard | Type | Action on trigger |
|-------|------|-------------------|
| Injection detector | Rule-based (no LLM) | Block |
| PII detector | LLM primary, regex fallback | Rewrite (scrub + continue) |
| Topic filter | Keyword fast-path + LLM | Block |
| Output guard | LLM (hallucination + tone) | Rewrite |

PII is never blocked — it's scrubbed and the cleaned query continues to P5. The original and scrubbed texts both appear in the LangSmith trace.

## Stack

- FastAPI (proxies to P5 with guard middleware)
- NVIDIA NIM (`nemotron-3-super-120b-a12b`) for LLM guards
- LangSmith for distributed tracing
- No database, no frontend (P6 is a backend-only proxy layer)

## Prerequisites

- **P5 must be running** on port 8000 before starting P6
- A LangSmith account with an API key (`LANGCHAIN_API_KEY`)

## Setup

```bash
cd p6-hardened-search/backend
pip install -r requirements.txt
cp .env.example .env            # fill in all keys
```

**backend/.env**
```
# NVIDIA (same as P5)
NVIDIA_API_KEY=nvapi-your-key-here
NVIDIA_BASE_URL=https://integrate.api.nvidia.com/v1
AGENT_MODEL=nvidia/nemotron-3-super-120b-a12b

# P5 backend URL
P5_BASE_URL=http://localhost:8000

# LangSmith
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=lsv2_your_langsmith_key_here
LANGCHAIN_PROJECT=p6-hardened-search
LANGCHAIN_ENDPOINT=https://api.smith.langchain.com
```

## Run

```bash
# Terminal 1 — start P5 first (from p5-product-search/backend/)
uvicorn main:app --port 8000

# Terminal 2 — start P6 (from p6-hardened-search/backend/)
uvicorn main:app --port 8001
```

Point your client or the P5 frontend at `http://localhost:8001/search` instead of P5 directly.

## Eval (input guards only, P5 not required)

```bash
# From p6-hardened-search/backend/
python ../eval/run_eval.py
```

Runs 15 adversarial queries (clean, injection, PII, off-topic) and reports pass/fail per guard decision.

## SSE events (same shape as P5, with two additions)

| Event type | When emitted |
|------------|-------------|
| `guard_blocked` | Injection or topic guard fired — request stopped |
| `guard_info` | PII or output guard rewrote something — request continues |
| `start`, `tool_call`, `tool_result` | Forwarded from P5 unchanged |
| `final_answer` | P5's answer, possibly rewritten by output guard |
| `done` | Stream complete |

## Project structure

```
p6-hardened-search/
  backend/
    guards/
      types.py              ← GuardResult dataclass
      injection_detector.py ← rule-based phrase + delimiter matching
      pii_detector.py       ← LLM primary, regex fallback
      topic_filter.py       ← keyword fast-path + LLM
      input_guard.py        ← orchestrates all three input checks
      output_guard.py       ← hallucination + tone check
    tracing/
      langsmith_tracer.py   ← configure() + request_trace()
    main.py                 ← FastAPI proxy + guard middleware
    requirements.txt
    .env.example
  eval/
    adversarial_queries.json ← 15 test cases (4 categories)
    run_eval.py              ← guard decision accuracy test
```
