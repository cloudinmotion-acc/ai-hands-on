# P8 - Eval Harness & Ship One Platform

Automated evaluation pipeline for the P7 Architect Bot. Runs 15 real-world design scenarios through the full P7 pipeline, judges every output with an LLM, verifies HITL edit propagation, and produces a GO / NO-GO verdict with a Next.js dashboard.

## What it evaluates

```
15 requirements → P7 API (auto-approve all stages)
  ↓
Trajectory evaluator    — did all 4 stages run in the right order?
Completeness evaluator  — LLM judge scores each stage against a 10-item checklist
Propagation test        — inject a HITL edit, check if HLD reflects it
  ↓
Scorecard → GO / NO-GO
  ↓
Next.js dashboard + results/latest.json
```

## Thresholds (all must pass for GO)

| Dimension | Threshold |
|---|---|
| Trajectory | ≥ 13/15 scenarios complete all 4 stages in order |
| Completeness — each stage | ≥ 70% average checklist coverage |
| Propagation | HITL edit must appear in the HLD |

## Stack

- **Eval backend:** Python, FastAPI, httpx (SSE client), openai SDK (NVIDIA NIM judge)
- **Dashboard:** Next.js 16, React 19, Tailwind CSS 4
- **CLI:** `run_eval.py` with rich progress table
- **CI:** GitHub Actions (or `act` for local simulation)

## Setup

```bash
cd p8-eval-harness/backend
pip install -r requirements.txt
cp .env.example .env       # fill in NVIDIA_API_KEY
```

**backend/.env**

```
NVIDIA_API_KEY=nvapi-your-key-here
JUDGE_MODEL=nvidia/nemotron-3-super-120b-a12b
P7_URL=http://localhost:8000
RESULTS_DIR=../results
CONCURRENCY=3
```

```bash
cd p8-eval-harness/frontend
npm install
```

## Run

### CLI (recommended for first run)

```bash
# Start P7 backend first
cd p7-full-version/backend
uvicorn main:app --port 8000

# In a new terminal:
cd p8-eval-harness/backend
python run_eval.py --quick          # 3 scenarios, ~10 min
python run_eval.py                  # all 15 scenarios, ~45 min
python run_eval.py --skip-propagation  # skip the HITL propagation test
```

### With dashboard (live progress)

```bash
# Terminal 1: P7 backend
uvicorn main:app --port 8000 --reload    (from p7-full-version/backend/)

# Terminal 2: P8 eval API
uvicorn main:app --port 8001             (from p8-eval-harness/backend/)

# Terminal 3: P8 dashboard
npm run dev                              (from p8-eval-harness/frontend/)
```

Open `http://localhost:3003`. Click **Run Eval** (or **Run Eval (quick)** for 3 scenarios).

### CI without pushing to GitHub (using act)

[act](https://github.com/nektos/act) runs GitHub Actions locally in Docker:

```bash
brew install act          # or choco install act-cli on Windows

# Dry run (no API calls):
act --dry-run push

# Real run (needs Docker):
act push --secret NVIDIA_API_KEY=nvapi-your-key
```

Or just run the CLI directly — it's the same command the CI calls:

```bash
python run_eval.py --quick --skip-propagation
```

## API endpoints (eval backend, port 8001)

| Method | Path | What it does |
|---|---|---|
| `GET` | `/health` | Liveness check |
| `GET` | `/results` | Serve latest.json |
| `POST` | `/eval/run` | SSE: run full pipeline, stream progress |

## SSE events (during eval run)

| Event | When |
|---|---|
| `eval_start` | Eval started, announces scenario count |
| `scenario_start` | A scenario session starting |
| `scenario_done` | Scenario finished with trajectory result |
| `completeness_start` | LLM judge starting |
| `completeness_done` | LLM judge finished |
| `propagation_start` | Propagation test starting |
| `propagation_done` | Propagation test result |
| `scorecard_ready` | Full results + verdict |
| `done` | Stream closed |

## Project structure

```
p8-eval-harness/
  backend/
    scenarios/
      requirements.json     ← 15 requirement strings with IDs and titles
    checklists/
      scoping.json          ← 10 checklist items per stage
      solution.json
      hld.json
      lld.json
    evaluators/
      trajectory.py         ← stage presence + order check (no LLM)
      completeness.py       ← LLM-as-judge per stage vs checklist
      propagation.py        ← HITL edit injection + keyword search
    runner.py               ← P7 API client, auto-approves all stages via SSE
    engine.py               ← orchestrates all evaluators with asyncio.gather
    scorecard.py            ← aggregates results into GO/NO-GO
    main.py                 ← FastAPI (GET /results, POST /eval/run SSE)
    run_eval.py             ← CLI entry point with rich progress table
    requirements.txt
    .env.example
  frontend/
    app/
      page.tsx              ← main dashboard (verdict + metrics + table)
      layout.tsx
      globals.css           ← dark ops theme, monospace scores
      api/
        results/route.ts    ← reads results/latest.json from filesystem
        eval/run/route.ts   ← SSE proxy to Python backend
    components/
      VerdictBanner.tsx     ← GO/NO-GO with pulse animation + blockers
      MetricCard.tsx        ← single dimension score card with bar
      ScenarioTable.tsx     ← expandable per-scenario results table
      PropagationCard.tsx   ← HITL edit injection details + evidence
      EvalProgress.tsx      ← live progress feed during eval run
    lib/
      types.ts
      api.ts
  results/                  ← auto-created; latest.json + timestamped reports
  .github/
    workflows/eval.yml      ← CI (manual_dispatch + push to p7 or p8 folders)
```

## How the propagation test works

1. Runs P7 on the LinkedIn post scheduler scenario
2. After scoping completes, edits the scoping output to inject: _"Must support full offline mode. Users should be able to draft and queue posts without internet connectivity, with local data sync when the connection is restored."_
3. Auto-approves solution using the edited scope
4. When HLD completes, searches for the word "offline" in the HLD content
5. PASS if found — the HITL edit propagated forward through the pipeline

This tests the core HITL → propagation guarantee: an edit made at stage N must influence the output of stage N+2.
