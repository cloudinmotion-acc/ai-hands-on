"""
P3 RAG Quality Gate — Evaluation Runner

Prerequisites:
  1. All 4 test docs ingested into P2 (product_manual.txt, company_policy.pdf,
     annual_report.pdf, quarterly_sales.xlsx)
  2. P2 backend running at P2_BASE_URL (default: http://localhost:8000)
  3. .env with NVIDIA_API_KEY (and optionally P2_BASE_URL)
  4. pip install -r requirements.txt

Run from this folder:
  python run_eval.py
"""

import sys
import types

# RAGAS hard-imports langchain_community.chat_models.vertexai at module load,
# but the module was removed in langchain-community 0.3+. We never use Vertex AI,
# so a stub satisfies the import without requiring a version downgrade.
if "langchain_community.chat_models.vertexai" not in sys.modules:
    _stub = types.ModuleType("langchain_community.chat_models.vertexai")
    _stub.ChatVertexAI = type("ChatVertexAI", (), {})
    sys.modules["langchain_community.chat_models.vertexai"] = _stub

import json
import os
import re
import textwrap
from datetime import datetime, timezone
from pathlib import Path

import httpx
import pandas as pd
from dotenv import load_dotenv
from openai import OpenAI
from tabulate import tabulate

load_dotenv()

NVIDIA_API_KEY  = os.getenv("NVIDIA_API_KEY", "")
P2_BASE_URL     = os.getenv("P2_BASE_URL", "http://localhost:8000")
NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"

# The model P2 uses to generate answers — same as your RAG pipeline
EVAL_MODEL  = os.getenv("EVAL_MODEL",  "nvidia/nemotron-3-super-120b-a12b")

# A DIFFERENT model used as judge + RAGAS scorer — must NOT be the same as EVAL_MODEL.
# gpt-oss-20b is a reasoning model: it produces chain-of-thought in reasoning_content
# before giving its final JSON answer, making it a stronger, less biased judge.
JUDGE_MODEL = os.getenv("JUDGE_MODEL", "openai/gpt-oss-20b")

EMBED_MODEL = "nvidia/nemotron-3-embed-1b"

THRESHOLDS = {
    "context_precision": 0.70,
    "context_recall":    0.60,
    "faithfulness":      0.80,
    "answer_relevancy":  0.70,
    "refusal_accuracy":  0.90,
}

HERE        = Path(__file__).parent
RESULTS_DIR = HERE / "results"
DATASET     = HERE / "dataset.json"
CHECKPOINT  = HERE / "results" / ".checkpoint.json"
CONFIG      = HERE / "eval_config.json"


# ── run configuration ────────────────────────────────────────────────────────
# Written by the P3 dashboard's settings panel; also editable by hand so a plain
# `python run_eval.py` from the terminal uses the same knobs as the UI.

DEFAULT_CONFIG = {
    "model":          EVAL_MODEL,
    "prompt_version": "v1",
    "top_k_chunks":   4,
    "llm_params": {
        "temperature":       0.2,
        "top_p":             0.7,
        "top_k":             40,
        "max_tokens":        1024,
        "frequency_penalty": 0.0,
        "enable_thinking":   False,
    },
    "judge_model":    JUDGE_MODEL,
    "judge_base_url": NVIDIA_BASE_URL,
    # Passed through as extra_body when set. On Ollama, "none" suppresses the
    # chain-of-thought: measured 14s per judge call versus 200-800s with it on,
    # and without it the reasoning consumes the whole token budget and the
    # content comes back empty. Leave blank for providers that reject the field.
    "judge_reasoning_effort": "",
    # Embeddings are a separate role from judging. answer_relevancy needs a real
    # embedding model, and a local chat model cannot serve /v1/embeddings — so
    # this stays on NVIDIA even when the judge is pointed at Ollama.
    "embed_model":    EMBED_MODEL,
    "embed_base_url": NVIDIA_BASE_URL,
}


def load_config() -> dict:
    cfg = json.loads(json.dumps(DEFAULT_CONFIG))  # deep copy
    if CONFIG.exists():
        try:
            with open(CONFIG) as f:
                user = json.load(f)
            for k, v in user.items():
                if k == "llm_params" and isinstance(v, dict):
                    cfg["llm_params"].update(v)
                elif k in cfg:
                    cfg[k] = v
        except Exception as e:
            print(f"  [config] ignoring {CONFIG.name}: {e}")
    return cfg


def config_fingerprint(cfg: dict) -> str:
    """
    Identifies the settings that shape phase-1 answers. A checkpoint recorded
    under different generation settings must not be reused, or a re-run would
    silently score the previous configuration's answers.
    """
    import hashlib
    keys = {k: cfg[k] for k in ("model", "prompt_version", "top_k_chunks", "llm_params")}
    return hashlib.sha256(json.dumps(keys, sort_keys=True).encode()).hexdigest()[:12]


CFG = load_config()


# ── checkpointing ────────────────────────────────────────────────────────────

def save_checkpoint(phase: int, rows: list[dict], fingerprint: str) -> None:
    RESULTS_DIR.mkdir(exist_ok=True)
    with open(CHECKPOINT, "w") as f:
        json.dump({"phase": phase, "rows": rows, "config": fingerprint}, f, indent=2)
    print(f"  [checkpoint] phase {phase} saved — safe to Ctrl+C and resume later.")


def load_checkpoint(fingerprint: str) -> tuple[int, list[dict]] | None:
    """
    Returns the checkpoint only if it was produced under the current generation
    settings. Reusing answers generated with a different model, prompt version
    or top_k would score the old configuration while reporting the new one.
    """
    if not CHECKPOINT.exists():
        return None
    with open(CHECKPOINT) as f:
        data = json.load(f)
    if data.get("config") != fingerprint:
        print("Settings changed since the last run — discarding stale checkpoint.")
        CHECKPOINT.unlink()
        return None
    return data["phase"], data["rows"]


# ── helpers ──────────────────────────────────────────────────────────────────

def _make_llm(model: str, temperature: float = 0.0, timeout: int = 300):
    """LangChain wrapper — used for RAGAS internal scoring."""
    from langchain_openai import ChatOpenAI
    return ChatOpenAI(
        model=model,
        base_url=NVIDIA_BASE_URL,
        api_key=NVIDIA_API_KEY,
        temperature=temperature,
        timeout=timeout,
        http_client=httpx.Client(verify=False),
    )


def _make_judge_client() -> OpenAI:
    """
    Raw OpenAI client for the judge — needed to access reasoning_content.
    base_url is configurable so the judge can point at a local OpenAI-compatible
    server (e.g. Ollama at http://localhost:11434/v1) instead of NVIDIA.
    """
    base_url = CFG.get("judge_base_url") or NVIDIA_BASE_URL
    # Local servers accept any non-empty key; NVIDIA needs the real one.
    api_key = NVIDIA_API_KEY or "local"
    return OpenAI(
        base_url=base_url,
        api_key=api_key,
        http_client=httpx.Client(verify=False),
    )


def _get_col(row: pd.Series, keyword: str) -> float:
    """Return first DataFrame column whose name contains keyword (case-insensitive)."""
    for col in row.index:
        if keyword.lower() in col.lower():
            v = row[col]
            return float(v) if v is not None and not pd.isna(v) else 0.0
    return 0.0


def is_refusal(answer: str) -> bool:
    lower = answer.lower()
    return "could not find" in lower or "not find" in lower or "not in the provided" in lower


# ── step 1: query P2 ─────────────────────────────────────────────────────────

def query_p2(question: str) -> dict:
    payload = {
        "question":       question,
        "model":          CFG["model"],
        "prompt_version": CFG["prompt_version"],
        "top_k_chunks":   CFG["top_k_chunks"],
        "llm_params":     CFG["llm_params"],
    }
    resp = httpx.post(f"{P2_BASE_URL}/query", json=payload, timeout=300)
    resp.raise_for_status()
    return resp.json()


# ── step 2: LLM-as-judge ─────────────────────────────────────────────────────

JUDGE_PROMPT = textwrap.dedent("""
    You are evaluating a RAG system answer. Output ONLY valid JSON — no prose, no markdown.

    Question: {question}
    Retrieved context (excerpt): {context}
    System answer: {answer}
    Ground truth: {ground_truth}

    Score on two dimensions (integer 1–5):
    - faithfulness: every factual claim in the answer is grounded in the context
      (5 = fully grounded, no hallucinations; 1 = major hallucinations)
    - correctness: the answer matches or covers the ground truth
      (5 = correct and complete; 1 = wrong or missing key facts)

    Output exactly: {{"faithfulness": N, "correctness": N, "reasoning": "one sentence"}}
""").strip()


def _coerce_score(value) -> int | None:
    """
    Accept a 1-5 score, reject anything else.

    Smaller instruct models answer the faithfulness/correctness fields with
    `true` instead of a number. bool is a subclass of int in Python, so a naive
    int() check turns that into 1 — a bottom score indistinguishable from a real
    measurement. Booleans and out-of-range values are rejected outright.
    """
    if isinstance(value, bool):
        return None
    try:
        n = int(round(float(value)))
    except (TypeError, ValueError):
        return None
    return n if 1 <= n <= 5 else None


def extract_judge_json(content: str) -> dict | None:
    """
    Pull the score object out of a judge response.

    Thinking models (gpt-oss, Qwen3) narrate before answering, and that narration
    routinely contains braces — so a greedy {.*} match spans from a brace inside
    the reasoning to the final one and fails to parse. Strip the think block,
    then scan for balanced objects and take the last one carrying the score keys.
    """
    body = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL | re.IGNORECASE)
    body = re.sub(r"^.*?</think>", "", body, flags=re.DOTALL | re.IGNORECASE)  # unclosed open
    body = re.sub(r"```(?:json)?|```", "", body)

    candidates: list[dict] = []
    depth = 0
    start = -1
    for i, ch in enumerate(body):
        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}" and depth:
            depth -= 1
            if depth == 0 and start >= 0:
                try:
                    obj = json.loads(body[start:i + 1])
                except json.JSONDecodeError:
                    continue
                if not isinstance(obj, dict):
                    continue
                f = _coerce_score(obj.get("faithfulness"))
                c = _coerce_score(obj.get("correctness"))
                if f is None or c is None:
                    continue
                candidates.append({
                    "faithfulness": f,
                    "correctness":  c,
                    "reasoning":    str(obj.get("reasoning", ""))[:400],
                })

    return candidates[-1] if candidates else None


def judge_answer(client: OpenAI, question: str, contexts: list[str], answer: str, ground_truth: str) -> dict:
    ctx_excerpt = "\n---\n".join(contexts)[:800]
    prompt = JUDGE_PROMPT.format(
        question=question,
        context=ctx_excerpt,
        answer=answer,
        ground_truth=ground_truth,
    )
    kwargs: dict = {}
    effort = (CFG.get("judge_reasoning_effort") or "").strip()
    if effort:
        kwargs["extra_body"] = {"reasoning_effort": effort}

    try:
        completion = client.chat.completions.create(
            model=CFG["judge_model"],
            messages=[{"role": "user", "content": prompt}],
            temperature=1,   # reasoning models require temperature=1
            top_p=1,
            max_tokens=4096,
            stream=False,
            **kwargs,
        )
        # Log the reasoning chain (chain-of-thought before final answer)
        reasoning = getattr(completion.choices[0].message, "reasoning_content", None)
        if reasoning:
            print(f"    [reasoning] {reasoning[:120].strip()}...")

        content = (completion.choices[0].message.content or "").strip()
        parsed = extract_judge_json(content)
        if parsed is not None:
            return parsed
        print(f"    judge returned unparseable output: {content[:120]!r}")
    except Exception as e:
        print(f"    judge error: {e}")
    # Neutral 3/3 keeps one bad response from dominating, but it is still a
    # fabricated score — the caller counts these so they can be reported.
    return {"faithfulness": 3, "correctness": 3, "reasoning": "parse error"}


# ── step 3: RAGAS ─────────────────────────────────────────────────────────────

def run_ragas(answerable_rows: list[dict]) -> pd.DataFrame:
    import warnings
    from openai import AsyncOpenAI, OpenAI
    from ragas import EvaluationDataset, SingleTurnSample, evaluate
    from ragas.llms import llm_factory
    from ragas.embeddings import OpenAIEmbeddings as RagasOpenAIEmbeddings
    # Use the old-style Metric subclasses — they pass the isinstance(m, Metric)
    # check inside evaluate(). The new ragas.metrics.collections classes use a
    # separate BaseMetric hierarchy incompatible with evaluate() in RAGAS 0.4.3.
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        from ragas.metrics import (
            _LLMContextPrecisionWithReference,
            _LLMContextRecall,
            _Faithfulness,
            _ResponseRelevancy,
        )

    judge_url   = CFG.get("judge_base_url") or NVIDIA_BASE_URL
    judge_model = CFG["judge_model"]
    embed_url   = CFG.get("embed_base_url") or NVIDIA_BASE_URL
    embed_model = CFG.get("embed_model") or EMBED_MODEL

    print(f"  RAGAS LLM  : {judge_model} @ {judge_url}")
    print(f"  RAGAS embed: {embed_model} @ {embed_url}")
    print(f"  concurrency: max_workers=2  (NVIDIA free-tier rate-limit guard)")

    # RAGAS scores with the same judge as the LLM-as-judge phase, so both halves
    # of the report come from one model. verify=False bypasses the corp proxy cert.
    _async_judge = AsyncOpenAI(
        base_url=judge_url,
        api_key=NVIDIA_API_KEY or "local",
        http_client=httpx.AsyncClient(verify=False),
    )
    # Embeddings use their own client: the judge may be a local chat model with
    # no /v1/embeddings route, while answer_relevancy always needs real vectors.
    # Sync, because _ResponseRelevancy calls embed_query/embed_documents from
    # inside RAGAS's async pipeline — asyncio.run() there would nest event loops.
    _sync_embed = OpenAI(
        base_url=embed_url,
        api_key=NVIDIA_API_KEY,
        http_client=httpx.Client(verify=False),
    )

    # Patch BEFORE llm_factory so LangChain captures the patched create reference.
    # Only needed for Ollama judges that require reasoning_effort via extra_body.
    _orig_ragas_create = _async_judge.chat.completions.create
    effort_default = (CFG.get("judge_reasoning_effort") or "").strip()

    if effort_default:
        async def _ragas_create_patched(*args, **kw):
            kw.setdefault("extra_body", {})["reasoning_effort"] = effort_default
            return await _orig_ragas_create(*args, **kw)
        _async_judge.chat.completions.create = _ragas_create_patched  # type: ignore[method-assign]

    ragas_llm = llm_factory(judge_model, client=_async_judge, temperature=1, max_tokens=2048)

    class _CompatEmbeddings(RagasOpenAIEmbeddings):
        """Adds LangChain-interface sync methods required by _ResponseRelevancy."""
        def embed_query(self, text: str) -> list[float]:
            resp = _sync_embed.embeddings.create(input=text, model=embed_model)
            return resp.data[0].embedding

        def embed_documents(self, texts: list[str]) -> list[list[float]]:
            resp = _sync_embed.embeddings.create(input=texts, model=embed_model)
            return [d.embedding for d in resp.data]

    ragas_embeddings = _CompatEmbeddings(client=_async_judge, model=embed_model)

    samples = [
        SingleTurnSample(
            user_input=r["question"],
            response=r["answer"],
            retrieved_contexts=r["contexts"],
            reference=r["ground_truth"],
        )
        for r in answerable_rows
    ]

    dataset = EvaluationDataset(samples=samples)
    # Metrics are instantiated with no args; evaluate() injects llm + embeddings.
    metrics = [
        _LLMContextPrecisionWithReference(),
        _LLMContextRecall(),
        _Faithfulness(),
        _ResponseRelevancy(strictness=1),
    ]
    # Throttle concurrency — RAGAS fires all 64 jobs at once by default, which
    # immediately saturates the NVIDIA free-tier rate limit and returns 0s for
    # every metric. max_workers=2 keeps it within quota without being too slow.
    try:
        from ragas import RunConfig
        _run_cfg = RunConfig(max_workers=2, max_retries=10, timeout=300)
    except Exception:
        _run_cfg = None

    eval_kwargs: dict = dict(
        dataset=dataset,
        metrics=metrics,
        llm=ragas_llm,
        embeddings=ragas_embeddings,
        raise_exceptions=False,
    )
    if _run_cfg is not None:
        eval_kwargs["run_config"] = _run_cfg

    result = evaluate(**eval_kwargs)
    return result.to_pandas()


# ── step 4: failure classification ───────────────────────────────────────────

def classify(r: dict) -> str:
    if not r["answerable"] and not is_refusal(r["answer"]):
        return "prompt"
    cp = r.get("context_precision") or 0
    cr = r.get("context_recall") or 0
    f  = r.get("faithfulness") or 0
    if cp < 0.5 and cr < 0.5:
        return "retrieval-miss"
    if cr >= 0.6 and f < 0.6:
        return "generation-error"
    if cp < 0.5 and cr >= 0.6:
        return "chunking"
    return "generation-error"


def composite_score(r: dict) -> float:
    return (
        (r.get("context_precision") or 0) * 0.20 +
        (r.get("context_recall")    or 0) * 0.20 +
        (r.get("faithfulness")      or 0) * 0.30 +
        (r.get("answer_relevancy")  or 0) * 0.20 +
        (r.get("judge_correctness", 3) / 5) * 0.10
    )


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    RESULTS_DIR.mkdir(exist_ok=True)

    with open(DATASET) as f:
        dataset = json.load(f)

    fingerprint = config_fingerprint(CFG)
    print("Run configuration:")
    print(f"  generator      : {CFG['model']}")
    print(f"  prompt version : {CFG['prompt_version']}")
    print(f"  top_k_chunks   : {CFG['top_k_chunks']}")
    print(f"  temperature    : {CFG['llm_params']['temperature']}")
    print(f"  judge          : {CFG['judge_model']} @ {CFG['judge_base_url']}")
    print()

    # ── Resume from checkpoint if available ─────────────────────────────────
    checkpoint = load_checkpoint(fingerprint)
    if checkpoint:
        done_phase, rows = checkpoint
        print(f"Resuming from checkpoint — phase {done_phase} already done ({len(rows)} rows loaded).")
    else:
        done_phase = 0
        rows = []

    # ── Phase 1: query P2 ───────────────────────────────────────────────────
    if done_phase < 1:
        print(f"Phase 1/3 — Querying P2 ({P2_BASE_URL}) for {len(dataset)} questions...")
        for i, item in enumerate(dataset, 1):
            label = item["question"][:65]
            print(f"  [{i:02d}/{len(dataset)}] {label}...")
            try:
                result   = query_p2(item["question"])
                answer   = result["answer"]
                contexts = [c["snippet"] for c in result.get("citations", [])]
            except Exception as e:
                print(f"    P2 error: {e}")
                answer   = "ERROR"
                contexts = []
            rows.append({
                **item,
                "answer":   answer,
                "contexts": contexts,
                "context_precision": None,
                "context_recall":    None,
                "faithfulness":      None,
                "answer_relevancy":  None,
            })
        save_checkpoint(1, rows, fingerprint)
    else:
        print(f"Phase 1/3 — skipped (loaded {len(rows)} P2 answers from checkpoint).")

    # ── Phase 2: LLM-as-judge ───────────────────────────────────────────────
    if done_phase < 2:
        print(f"\nPhase 2/3 — LLM-as-judge ({len(rows)} rows) using {CFG['judge_model']}...")
        judge_client = _make_judge_client()
        for i, r in enumerate(rows, 1):
            print(f"  [{i:02d}/{len(rows)}] judging...")
            scores = judge_answer(judge_client, r["question"], r["contexts"], r["answer"], r["ground_truth"])
            r["judge_faithfulness"] = scores.get("faithfulness", 3)
            r["judge_correctness"]  = scores.get("correctness",  3)
            r["judge_reasoning"]    = scores.get("reasoning",    "")
            r["judge_parse_error"]  = scores.get("reasoning") == "parse error"

        n_bad = sum(1 for r in rows if r.get("judge_parse_error"))
        if n_bad:
            print(
                f"\n  WARNING: {n_bad}/{len(rows)} judge responses could not be parsed and "
                f"defaulted to 3/3. Those judge scores are not real measurements."
            )
        save_checkpoint(2, rows, fingerprint)
    else:
        print(f"Phase 2/3 — skipped (judge scores loaded from checkpoint).")

    # ── Phase 3: RAGAS (answerable rows only) ───────────────────────────────
    answerable = [r for r in rows if r["answerable"] and r["answer"] != "ERROR"]
    print(f"\nPhase 3/3 — RAGAS on {len(answerable)} answerable rows (calls NVIDIA API — be patient)...")
    ragas_df = run_ragas(answerable)

    for i, r in enumerate(answerable):
        row = ragas_df.iloc[i]
        r["context_precision"] = _get_col(row, "precision")
        r["context_recall"]    = _get_col(row, "recall")
        r["faithfulness"]      = _get_col(row, "faithfulness")
        r["answer_relevancy"]  = _get_col(row, "relevancy")

    # ── Phase 4: refusal accuracy ───────────────────────────────────────────
    unanswerable = [r for r in rows if not r["answerable"]]
    correct_refusals = sum(1 for r in unanswerable if is_refusal(r["answer"]))
    refusal_accuracy = correct_refusals / len(unanswerable) if unanswerable else 1.0

    # ── Phase 5: aggregates + thresholds ────────────────────────────────────
    def avg(key):
        vals = [r[key] for r in answerable if r.get(key) is not None]
        return sum(vals) / len(vals) if vals else 0.0

    aggregates = {
        "context_precision": avg("context_precision"),
        "context_recall":    avg("context_recall"),
        "faithfulness":      avg("faithfulness"),
        "answer_relevancy":  avg("answer_relevancy"),
        "refusal_accuracy":  refusal_accuracy,
    }

    # ── Phase 6: composite + failure classification ──────────────────────────
    for r in rows:
        r["composite"]      = composite_score(r)
        r["classification"] = classify(r)

    bottom5 = sorted(answerable, key=lambda r: r["composite"])[:5]

    # ── Print results ────────────────────────────────────────────────────────
    print("\n" + "=" * 62)
    print("METRIC SUMMARY")
    print("=" * 62)
    overall_pass = True
    threshold_rows = []
    for metric, val in aggregates.items():
        threshold = THRESHOLDS[metric]
        passed = val >= threshold
        if not passed:
            overall_pass = False
        threshold_rows.append([
            metric,
            f"{val:.3f}",
            f">= {threshold:.2f}",
            "PASS ✓" if passed else "FAIL ✗",
        ])
    print(tabulate(threshold_rows, headers=["Metric", "Score", "Threshold", "Result"], tablefmt="simple"))

    print("\n" + "=" * 62)
    print("TOP-5 WORST QUESTIONS")
    print("=" * 62)
    worst_rows = [
        [r["id"], textwrap.shorten(r["question"], 42), f"{r['composite']:.2f}", r["classification"]]
        for r in bottom5
    ]
    print(tabulate(worst_rows, headers=["ID", "Question", "Score", "Root cause"], tablefmt="simple"))

    print("\n" + ("=" * 62))
    verdict = "OVERALL: PASS — ready to ship" if overall_pass else "OVERALL: FAIL — fix failures before shipping"
    print(verdict)
    print("=" * 62)

    # ── Write JSON report ────────────────────────────────────────────────────
    report = {
        "run_at":       datetime.now(timezone.utc).isoformat(),
        "eval_model":   CFG["model"],
        "judge_model":  CFG["judge_model"],
        # Full settings so a report can be traced back to the run that produced it.
        "config":       CFG,
        # Judge responses that failed to parse and fell back to a neutral 3/3.
        "judge_parse_errors": sum(1 for r in rows if r.get("judge_parse_error")),
        "aggregates":   aggregates,
        "thresholds":   THRESHOLDS,
        "overall_pass": overall_pass,
        "per_question": rows,
    }
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    report_path = RESULTS_DIR / f"report_{ts}.json"
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)
    print(f"\nFull report: {report_path}")

    # Clean up checkpoint — run completed successfully
    CHECKPOINT.unlink(missing_ok=True)


if __name__ == "__main__":
    if not NVIDIA_API_KEY:
        sys.exit("ERROR: NVIDIA_API_KEY not set — add it to p3-rag-eval/.env")
    main()
