# P3 — RAG Quality Gate · Demo Notes

---

## The Problem

You've built a RAG system (P2). It looks like it's working. The answers seem reasonable. But "seems reasonable" is not a release standard — it's a gut feeling. Two weeks later someone asks a question your RAG answers wrongly and you have no idea whether this is a new regression or something that was always broken.

The deeper problem is that RAG failures have multiple root causes that look identical to the end user — a wrong answer could mean:
- The retrieval found the wrong chunks (retrieval failure)
- The retrieval found the right chunks but the LLM ignored them (faithfulness failure)
- The LLM answered a question the document doesn't contain (refusal failure)

You can't fix what you can't measure. And you can't measure with your eyes.

---

## The Solution

An automated evaluation pipeline with four layers:

1. **RAGAS metrics** — automated scores for context precision, context recall, faithfulness, and answer relevancy across 20 pre-written Q&A pairs
2. **LLM-as-judge** — a second model scores each answer on faithfulness (1–5) and correctness (1–5) with reasoning
3. **Refusal accuracy** — 4 unanswerable questions that the system must refuse to answer correctly
4. **Release thresholds** — every metric has a PASS/FAIL threshold, and a failure is classified by root cause so you know where to look

The output is a timestamped JSON report and a Streamlit dashboard showing trends across runs.

---

## What Makes This Different

**vs. "eyeballing" (what most teams do):**
Eyeballing doesn't scale, isn't reproducible, and can't tell you which component is failing. This pipeline produces the same numbers every run, on the same dataset, with clear failure attribution. Run it before every deploy — if a metric drops, you know before users do.

**vs. other eval frameworks (TruLens, DeepEval):**
Those frameworks are great but abstract away the mechanics. P3 shows you exactly how each metric is computed and lets you see the RAGAS internals. Understanding the mechanism means you can debug unexpected scores, not just accept them.

**vs. simple unit tests:**
Unit tests check code correctness. RAG eval checks answer quality — a fundamentally different and harder problem. "Is `similarity_search()` returning 4 results?" is a unit test. "Are those 4 results the right ones for this question?" is an eval. Both are necessary; most teams only write the first.

---

## Demo Tour

### Before you start
- [ ] P2 backend running on port 8000 with all 4 documents ingested:
  `product_manual.txt`, `company_policy.pdf`, `annual_report.pdf`, `quarterly_sales.xlsx`
- [ ] `python run_eval.py` has been run at least once (to generate a results file)
- [ ] Dashboard: `streamlit run dashboard.py` from `p3-rag-eval/`

---

### Step 1 — Open the dashboard
**Open:** `http://localhost:8501`

**Say:**
> "This is the RAG Quality Gate dashboard. Every time we run the eval script, it produces a report. The dashboard reads all the reports and shows trends over time. Right now I'm showing you the results from the most recent run."

---

### Step 2 — Walk through the metric summary
**Do:** Point to the 5 metrics (context precision, recall, faithfulness, answer relevancy, refusal accuracy) and their PASS/FAIL status.

**Say:**
> "These five numbers are our release criteria. Think of them like test coverage thresholds — if any one drops below its threshold, the build fails. Let me explain what each one means:"
>
> - **Context precision:** Of the chunks we retrieved, how many were actually relevant? High precision = no junk in the context.
> - **Context recall:** Of all the relevant chunks that exist, did we retrieve them? High recall = we didn't miss anything important.
> - **Faithfulness:** Does the answer only say things that are in the retrieved chunks? Measures hallucination.
> - **Answer relevancy:** Is the answer actually about the question? Catches vague or off-topic responses.
> - **Refusal accuracy:** When asked something the document doesn't contain, does it refuse correctly?

---

### Step 3 — Show per-question breakdown
**Do:** Scroll to the per-question table, point to a low-scoring row.

**Say:**
> "Here's where it gets useful. This isn't just one average number — it's a score per question. If question 7 has low faithfulness but high recall, that tells us the retrieval is working but the LLM is going off-script for that question. That's a prompting problem, not a retrieval problem. Different fix for each root cause."

---

### Step 4 — Show the LLM-as-judge section
**Do:** Click into a specific question's detail panel.

**Say:**
> "Beyond RAGAS, we run a second LLM as a judge — completely separate from the RAG system. It reads the question, the retrieved context, the system's answer, and the ground truth we wrote, then scores faithfulness and correctness 1–5 with a written explanation. This catches things RAGAS misses — like when an answer is technically grounded but completely misunderstands the question."

---

### Step 5 — Show the failure classification
**Do:** Point to the bottom-5 failure section.

**Say:**
> "The bottom 5 worst questions are shown with a failure classification — retrieval-miss, generation-error, or prompt issue. This is the actionable output. If I see 'retrieval-miss' for multiple questions, I know to look at chunking strategy or embedding model. If I see 'generation-error', the LLM is hallucinating — look at the prompt constraints."

---

### Step 6 — (If time) Show the run script
**Do:** Open `run_eval.py` briefly, show the three-phase structure.

**Say:**
> "The script runs three phases: query P2 for all 20 questions, run RAGAS on the collected data, run the LLM judge. Results get written to a timestamped JSON file. You can run this in CI — if any metric drops, fail the pipeline."

---

## Code Walkthrough

### `dataset.json` — the 20 Q&A pairs
**What it does:** The ground truth. 16 answerable questions (4 per document) + 4 unanswerable questions. Each has the question, the correct answer, which document it comes from, and whether it's answerable.

The unanswerable questions are the most important test: "What is the CEO's name?" and "When was the company founded?" don't appear in any document. The system must say "I could not find this" — not hallucinate an answer. `refusal_accuracy` measures this.

Writing good eval data is harder than it looks — the questions need to be answerable from the document (not from general knowledge), and the ground truth needs to exactly match what the document says.

---

### `run_eval.py` — three-phase evaluation runner
**What it does:** Orchestrates the full eval: queries P2, collects answers and citations, runs RAGAS, runs the LLM judge, applies thresholds, writes report.

**Key function: RAGAS setup**
```python
from ragas import evaluate
from ragas.metrics import (
    _LLMContextPrecisionWithReference,
    _LLMContextRecall,
    _Faithfulness,
    _ResponseRelevancy,
)
```
Important: RAGAS 0.4.3 uses private class names (prefixed with `_`). This is a hard-won quirk — the public API changed between versions and the private names are what actually work with `evaluate()`. Don't swap these for the public collection classes — they're not compatible.

**Key function: LLM-as-judge prompt**
The judge gets: question + retrieved context + system answer + ground truth. It returns JSON with `faithfulness` (1–5), `correctness` (1–5), and `reasoning`. Temperature = 1 is required for the judge model (`gpt-oss-20b`) — this is another RAGAS quirk where the judge model behaves strangely at temperature 0.

**Failure classification logic:** After scoring, questions are ranked by composite score. The bottom 5 get classified by pattern:
- Low precision + low recall → retrieval-miss (wrong chunks being fetched)
- High recall + low faithfulness → generation-error (LLM ignoring the context)
- Low precision + high recall → chunking issue (chunks are too large, pulling irrelevant text)

---

### `dashboard.py` — Streamlit results viewer
**What it does:** Reads all JSON files in `results/`, shows the latest run's metrics, per-question breakdown, trend chart across runs, and the failure report.

The dashboard is read-only — it never calls P2. It just reads the files that `run_eval.py` wrote. This means you can review results without the backend running, and share result files with teammates who don't have the full stack set up.

---

## New Concepts to Stress

### RAGAS Metrics
RAGAS (Retrieval Augmented Generation Assessment) is an open-source framework specifically built for evaluating RAG pipelines. The four core metrics:

- **Context Precision** — uses the LLM to judge whether each retrieved chunk was actually relevant to the question. Measures signal-to-noise in retrieval.
- **Context Recall** — uses the ground truth answer to check whether all the necessary information was retrieved. Measures completeness of retrieval.
- **Faithfulness** — uses the LLM to check whether every claim in the answer is supported by the context. This is the hallucination detector.
- **Answer Relevancy** — embeds the answer and the question, measures semantic similarity. Catches verbose or tangential answers.

Each metric makes 1–4 internal LLM calls per question — eval is expensive. For 20 questions across 4 metrics, expect 80–120 LLM calls per run.

### LLM-as-Judge
Using a language model to evaluate another language model's output. The key design principle: the judge model should be different from (or at least separately prompted from) the generator model, so you're not just asking the same model to approve its own output. Used by OpenAI for RLHF training, by RAGAS for metric computation, and here as an independent quality signal.

### Release Thresholds
The principle that automated systems need objective gates before deployment. In software engineering this is test coverage — "don't deploy below 80% coverage." In AI engineering this is metric thresholds — "don't deploy if faithfulness < 0.80." The thresholds are arbitrary starting points; they should be calibrated against your actual business tolerance for wrong answers.

---

## Conclusion

P3 closes the loop that P2 opened. P2 builds the RAG. P3 measures whether it actually works — and tells you where it's failing and why. Together they demonstrate a complete AI engineering discipline: build, measure, iterate.

**Key takeaway for the room:** In AI engineering, evaluation is not optional. "It looks good" ships bugs. A quality gate with reproducible numbers is what makes AI systems maintainable over time.
