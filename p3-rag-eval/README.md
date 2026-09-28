# P3 — RAG Quality Gate

Automated evaluation of P2's retrieval and answer quality using RAGAS metrics + an LLM-as-judge. Replaces "it looks good" with reproducible numbers and PASS/FAIL thresholds.

## What it does

- Runs 20 pre-written Q&A pairs against the live P2 backend
- Scores each answer on 4 RAGAS metrics (context precision, recall, faithfulness, relevancy)
- Runs an LLM-as-judge pass (faithfulness 1–5, correctness 1–5)
- Measures refusal accuracy on 4 unanswerable questions
- Writes a timestamped JSON report + shows a Streamlit dashboard

## Stack

- Python CLI (`run_eval.py`) + Streamlit dashboard (`dashboard.py`)
- RAGAS 0.4.3 for automated metrics
- NVIDIA NIM for generator + judge LLM
- No database of its own — calls P2 over HTTP

## Prerequisites

**P2 must be running** with all 4 test documents ingested:
- `product_manual.txt`
- `company_policy.pdf`
- `annual_report.pdf`
- `quarterly_sales.xlsx`

Upload these via the P2 UI or `POST /ingest` before running eval.

## Setup

```bash
cd p3-rag-eval
pip install -r requirements.txt
cp .env.example .env        # fill in NVIDIA_API_KEY
```

**.env**
```
NVIDIA_API_KEY=nvapi-your-key-here
P2_BASE_URL=http://localhost:8000
```

## Run

```bash
# Run evaluation (from p3-rag-eval/)
python run_eval.py

# View results dashboard (from p3-rag-eval/)
streamlit run dashboard.py
```

Dashboard opens at `http://localhost:8501`.

## Release thresholds

| Metric | Threshold |
|--------|-----------|
| Context precision | ≥ 0.70 |
| Context recall | ≥ 0.60 |
| Faithfulness | ≥ 0.80 |
| Answer relevancy | ≥ 0.70 |
| Refusal accuracy | ≥ 0.90 |

Anything below threshold → FAIL with root cause classification (retrieval-miss, generation-error, prompt issue).

## Project structure

```
p3-rag-eval/
  run_eval.py       ← main evaluation runner
  dashboard.py      ← Streamlit results viewer
  dataset.json      ← 20 Q&A pairs (16 answerable + 4 unanswerable)
  eval_config.json  ← model + threshold settings
  results/          ← auto-created, one report_<timestamp>.json per run
  requirements.txt
  .env.example
```
