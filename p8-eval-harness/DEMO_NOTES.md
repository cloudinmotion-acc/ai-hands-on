# P8 - Eval Harness & Ship One Platform · Demo Notes

---

## The Problem

Every AI portfolio shows a system doing something impressive. Almost none of them show how you'd know if it's working reliably.

P7 is a stateful, multi-agent pipeline with human review gates. How do you verify that it:
- Consistently produces all 4 design stages across different requirement types?
- Generates substantively complete outputs — not just long text, but covering the right topics?
- Actually propagates human edits forward (the whole point of HITL)?

Without a test harness, you have one demo. With one, you have evidence.

---

## What P8 Does

Runs 15 real-world requirements through the full P7 pipeline, evaluates every output, and renders a GO / NO-GO verdict with three independent dimensions.

```
15 diverse requirements
  ↓ P7 API runner (concurrent sessions, auto-approve)
  ↓
  ├── Trajectory eval    — did all 4 stages complete in order?
  ├── Completeness eval  — LLM-as-judge vs 40 checklist items (10 per stage)
  └── Propagation test   — inject HITL edit → verify it reaches HLD
  ↓
Scorecard: GO if all three dimensions meet threshold
  ↓
Next.js dashboard + JSON artifact + GitHub Actions CI
```

---

## The Three Evaluators

### 1. Trajectory evaluator (`evaluators/trajectory.py`)
- No LLM. Pure logic.
- Checks that the P7 session completed all 4 stages: scoping → solution → HLD → LLD
- Checks that they ran in the correct order (no stage ran before its predecessor)
- PASS per scenario if all 4 stages present and ordered
- **Threshold:** ≥ 13/15 scenarios PASS (87%)

**Why this matters:** A system that hallucinated an HLD without running a scoping stage would pass a vibe check but fail here. The trajectory eval catches pipeline integrity failures.

### 2. Completeness evaluator (`evaluators/completeness.py`)
- LLM-as-judge. The nemotron model evaluates each stage output against a 10-item checklist.
- Checklist items are things like: "identifies primary user types", "proposes a database solution", "includes at least one API endpoint definition with HTTP method and path"
- LLM returns a JSON array of 0/1 scores, one per item
- Score = items_satisfied / total_items, per stage, averaged across scenarios
- **Threshold:** ≥ 70% average per stage

**Why this matters:** A stage can be long, confident, and completely miss half the required content. The checklist is the objective specification of what a good design document contains. The LLM judge turns it into a reproducible score.

### 3. Propagation test (`evaluators/propagation.py`)
- The only test that exercises the HITL mechanism directly.
- Runs the LinkedIn post scheduler requirement through scoping normally
- When scoping is approved, **instead of plain approve**, injects a constraint into the scoping content: _"Must support full offline mode with local data sync when connection is restored"_
- Submits the edited content as a HITL edit (POST /resume with action="edit")
- Auto-approves solution using the edited scope
- When HLD completes, checks if the word "offline" appears anywhere in the HLD content
- PASS = the human-injected constraint reached the HLD

**Why this matters:** This is the core behavioral guarantee of P7. If you edit stage N, the downstream agents should receive your version, not the original. If this test fails, the HITL pattern is broken at the data-flow level.

---

## 82% Is Still NO-GO

The verdict logic is AND, not OR:
- Trajectory ≥ 87% AND all stage completeness ≥ 70% AND propagation PASS

A system with 14/15 trajectory PASS and 82% completeness but a failed propagation test gets NO-GO. That's the point — 82% overall readiness with a broken core mechanism is not production-ready.

**Narration point:** "Every non-trivial AI system needs a test harness. Not because the AI is unreliable, but because you need to know which dimension is failing when it does. Is it retrieval? Is it generation? Is it the human-in-the-loop mechanism? P8 isolates each dimension."

---

## Demo Setup

- [ ] P7 backend running: `uvicorn main:app --port 8000` from `p7-full-version/backend/`
- [ ] P8 eval backend: `uvicorn main:app --port 8001` from `p8-eval-harness/backend/`
- [ ] P8 dashboard: `npm run dev` from `p8-eval-harness/frontend/` (port 3003)
- [ ] `.env` files in both backends have `NVIDIA_API_KEY`
- [ ] Have pre-computed `results/latest.json` ready (see next section)

**Recommended demo approach:** Show pre-computed results in the dashboard (instant, no waiting), then show the CLI running `--quick` live to demonstrate actual execution.

---

## Pre-computing Results for Demo

Run this once before the demo (takes ~10 min for quick mode):

```bash
cd p8-eval-harness/backend
python run_eval.py --quick --skip-propagation
```

This writes `results/latest.json` which the dashboard loads immediately on page open.

If you want a "full" results file to show in the dashboard (better numbers, all 15 scenarios), run the full eval once when you have time (~45 min) and save a copy:

```bash
python run_eval.py
cp ../results/latest.json ../results/full_results_backup.json
```

---

## Demo Tour

### Step 1 — Show the dashboard (pre-loaded results)

Open `http://localhost:3003`.

**Point to the verdict banner:**
> "The GO / NO-GO verdict is the output of three independent evaluation dimensions. Not a vibe check — an automated test harness. Let me show you what each one measures."

**Point to the four metric cards:**
> "Trajectory: 14 out of 15 scenarios completed all four design stages. Completeness: the LLM judge scored each stage output against a 10-item checklist. Propagation: binary pass or fail — did a human edit actually reach the next stage?"

---

### Step 2 — Stage completeness breakdown

Point to the four stage bars (Scoping, Solution, HLD, LLD).

> "Each bar is the average score across all 15 scenarios for that stage. LLD is usually the hardest — it has to produce DDL, API contracts, and a processing flow. A score below 70% on any single stage is an immediate NO-GO even if everything else is fine."

---

### Step 3 — Scenario table

Click a scenario row to expand it.

> "This is what the evaluator saw for each individual run. Scoping 80%, HLD 70%, LLD 60% — the LLD is the weakest stage. If I were shipping this, I'd rewrite the LLD prompt and re-run to see if the score moves."

**Narration point:** "This is what a production AI engineering workflow looks like. You have an evaluation harness, you make a change to the system, you re-run the eval, you check if the score improved. Same as unit tests in software engineering."

---

### Step 4 — Propagation card

Scroll to the propagation card.

> "This is the most important test in the whole harness. I injected this sentence into the scoping output: 'Must support full offline mode with local data sync.' Then I let the solution and HLD agents run using that edited scope. I found the word 'offline' in the HLD — the edit propagated. If it hadn't, P7's HITL mechanism would be broken."

**Show the evidence quote (from the HLD):**
> "The system includes an offline-first module…" — verbatim from the HLD. The agent received the edited scope and designed around the offline constraint.

---

### Step 5 — Run live (quick mode)

Click **Quick ON**, then **Run Eval (quick)**.

Watch the progress feed:
- Scenario 1/3: LinkedIn Post Scheduler — trajectory PASS
- Scenario 2/3: Corporate Expense Management — trajectory PASS
- Scenario 3/3: Retail Inventory Tracker — PASS
- Completeness judge running…
- Scorecard ready — GO

**Say:**
> "That's three real scenarios through the full P7 pipeline, evaluated in real time. Each scenario made five SSE requests to P7, ran the graph through all four stages, and then the LLM judge scored each stage output against 40 checklist items. The result you see is not a mock — it's a live evaluation."

---

### Step 6 — CLI and CI

Show the terminal:

```bash
cd p8-eval-harness/backend
python run_eval.py --quick
```

> "Same eval, same results, from the command line. This is what runs in CI — GitHub Actions calls this exact command. If the verdict is NO-GO, the CI pipeline fails. If it's GO, the artifacts go to the next step."

Show `.github/workflows/eval.yml`:

> "The workflow triggers on any push to P7 or P8 folders. It starts P7, runs the eval, uploads the results JSON as an artifact, and fails the build if the verdict isn't GO. That's the pipeline that catches regressions before they ship."

**On not having a GitHub repo:** "If you don't push to GitHub, this same command runs identically locally. The CI YAML is there to show how you'd wire it up — and you can run the exact same thing locally with `act`, which simulates GitHub Actions in Docker."

---

## Code Walkthrough

### `runner.py` — P7 API client

```python
async def _stream_to_interrupt(client, method, url, body):
    async with client.stream(method, url, json=body) as response:
        async for event in _read_sse(response):
            if event.get("type") == "stage_complete":
                outputs[stage] = content
            elif event.get("type") == "awaiting_review":
                return ("awaiting", stage)
            elif event.get("type") == "session_complete":
                return ("complete", None)
```

**Why not just poll the state endpoint?** The SSE stream is the only way to capture stage content at the moment the node completes. The state endpoint gives you the same content, but polling it introduces a race with the checkpoint write. The stream is always ahead of the checkpoint.

---

### `evaluators/completeness.py` — LLM judge

```python
JUDGE_PROMPT = """
You are a senior software architect evaluating a technical design document.
...
For each item, output 1 if clearly addressed, 0 if absent or vague.
Output ONLY valid JSON: {"scores": [1, 0, 1, ...]}
"""
```

**Why not ask the LLM to score the whole document at once?** Because a single holistic score doesn't tell you which checklist items are missing. The per-item binary score turns the LLM's judgment into an actionable diagnostic: "your LLD is missing API error response definitions" is more useful than "your LLD scored 65%."

---

### `evaluators/propagation.py` — HITL test

```python
result = await run_scenario(
    requirement=TEST_REQUIREMENT,
    p7_url=config.p7_url,
    session_id=session_id,
    edit_at={"stage": "scoping", "inject": INJECTION_TEXT},
)
hld_content = result["outputs"].get("hld", "")
found = SEARCH_TERM.lower() in hld_content.lower()
```

The propagation test is the integration test for the HITL mechanism. Unit tests check that individual endpoints work. Integration tests check that the data flows correctly across the whole system. This is the integration test.

---

### `engine.py` — Concurrent orchestration

```python
tasks = [_run_one(i, sc) for i, sc in enumerate(scenarios)]
ordered_results = await asyncio.gather(*tasks)

completeness_results, propagation_result = await asyncio.gather(
    _run_completeness(), _run_propagation()
)
```

Three levels of concurrency:
1. Scenarios run concurrently (semaphore limits to 3 at a time)
2. LLM completeness calls run concurrently across scenarios and stages
3. Completeness eval and propagation test run concurrently

Without concurrency, the full 15-scenario eval would take 3–4 hours. With it, it takes ~45 minutes. This is what async Python is for.

---

## New Concepts to Stress

### LLM-as-Judge
Using one LLM to evaluate the output of another. Standard in production AI evaluation — the judge is not checking correctness (it doesn't have a ground truth), it's checking completeness: are the expected elements present? The 10-item checklist is the specification. The LLM judge turns natural-language checklist items into a binary score without requiring you to write regex or keyword matchers for every possible way an agent might express "I recommend PostgreSQL."

### Automated vs. Human Evaluation
Human evaluation is the gold standard but doesn't scale. You can't have a senior engineer read 60 design documents (15 scenarios × 4 stages) after every code change. Automated evaluation doesn't replace human judgment — it filters which runs need human attention. If completeness drops from 82% to 65% after a prompt change, a human should read those outputs. If it stays stable, you don't need to.

### Evaluation as Regression Test
The eval harness is not just for initial validation — it's what you run after every change to P7's prompts or pipeline. You make a change, re-run the eval, compare the scorecard to the previous run. If trajectory drops by 2 scenarios, you introduced a regression. The CI enforces this by failing the build on NO-GO, making the evaluation a gate before any code reaches the main branch.

### Three-Dimension Quality Model
A system can look great on one dimension and fail another. High trajectory + high completeness + failed propagation = NO-GO, because the core mechanism is broken. This is why the verdict is AND, not OR. In production AI systems, you always need at least trajectory (did it run?), quality (was the output good?), and behavioral (did the system do what it's supposed to do?). P8 maps cleanly to those three.

---

## Conclusion

P8 closes the portfolio loop. P1 to P7 built increasingly sophisticated AI systems. P8 answers the question every interviewer will ask: "How do you know it works?"

The answer is not "I tested it manually." The answer is:
1. A reproducible evaluation pipeline with 15 scenarios
2. Three independent evaluation dimensions with explicit thresholds
3. A GO/NO-GO verdict that runs in CI on every push
4. A dashboard that shows which dimension failed and why

That's production AI engineering. Not just building the system — building the system that tells you when the system breaks.
