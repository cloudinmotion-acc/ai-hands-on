"""
P5 Eval — precision@5 comparison across three retrieval modes.

For each of the 15 queries, runs all three retrieval modes:
  1. vector_only     — vector_retriever.search() alone
  2. bm25_only       — bm25_retriever.search() alone
  3. hybrid (full)   — sql + bm25 + vector → RRF merge (via mcp_server)

Metrics per mode:
  - precision@5        : fraction of top-5 results in expected_ids
                         (only meaningful for queries with known expected_ids)
  - recall@5           : fraction of expected_ids found in top-5
  - result_count       : how many products returned
  - decomposed_filters : what LLM extracted (hybrid only)

Writes results/report_<timestamp>.json and prints a summary table.

Run from p5-product-search/:
    python eval/run_eval.py
"""

import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

# Bootstrap path so we can import from backend/
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from dotenv import load_dotenv
load_dotenv(ROOT / "backend" / ".env")

from search import bm25_retriever, vector_retriever, decomposer, sql_filter, merger
from mcp_server import search_products


QUERIES_PATH = Path(__file__).parent / "queries.json"
RESULTS_DIR  = Path(__file__).parent / "results"
TOP_K = 5


def precision_at_k(results: list[dict], expected_ids: list[int], k: int) -> float:
    if not expected_ids:
        return -1.0  # sentinel — not measurable
    top_ids = [r["id"] for r in results[:k]]
    hits = sum(1 for pid in top_ids if pid in expected_ids)
    return hits / min(k, len(top_ids)) if top_ids else 0.0


def recall_at_k(results: list[dict], expected_ids: list[int], k: int) -> float:
    if not expected_ids:
        return -1.0
    top_ids = [r["id"] for r in results[:k]]
    hits = sum(1 for eid in expected_ids if eid in top_ids)
    return hits / len(expected_ids)


def run_query(query_obj: dict) -> dict:
    q   = query_obj["query"]
    exp = query_obj.get("expected_ids", [])

    # Mode 1 — BM25 only
    bm25_res = bm25_retriever.search(q, top_k=TOP_K)

    # Mode 2 — Vector only
    vec_res = vector_retriever.search(q, top_k=TOP_K)

    # Mode 3 — Full hybrid (decompose → sql + bm25 + vector → RRF)
    raw = search_products(query=q, top_k=TOP_K)
    hybrid_data = json.loads(raw)
    hybrid_res  = hybrid_data["results"]
    decomposed  = hybrid_data["decomposed"]

    return {
        "id":    query_obj["id"],
        "query": q,
        "mode_hint": query_obj.get("mode"),
        "expected_ids": exp,
        "bm25": {
            "results":      bm25_res[:TOP_K],
            "precision@5":  precision_at_k(bm25_res, exp, TOP_K),
            "recall@5":     recall_at_k(bm25_res, exp, TOP_K),
            "result_count": len(bm25_res),
        },
        "vector": {
            "results":      vec_res[:TOP_K],
            "precision@5":  precision_at_k(vec_res, exp, TOP_K),
            "recall@5":     recall_at_k(vec_res, exp, TOP_K),
            "result_count": len(vec_res),
        },
        "hybrid": {
            "decomposed":   decomposed,
            "results":      hybrid_res[:TOP_K],
            "precision@5":  precision_at_k(hybrid_res, exp, TOP_K),
            "recall@5":     recall_at_k(hybrid_res, exp, TOP_K),
            "result_count": len(hybrid_res),
        },
    }


def print_summary(rows: list[dict]) -> None:
    header = f"{'#':>2}  {'Query':<42}  {'BM25 P@5':>8}  {'Vec P@5':>8}  {'Hybrid P@5':>10}"
    print("\n" + "─" * len(header))
    print(header)
    print("─" * len(header))
    for r in rows:
        b = r["bm25"]["precision@5"]
        v = r["vector"]["precision@5"]
        h = r["hybrid"]["precision@5"]
        fmt = lambda x: f"{x:.2f}" if x >= 0 else "  n/a"
        print(f"{r['id']:>2}  {r['query'][:42]:<42}  {fmt(b):>8}  {fmt(v):>8}  {fmt(h):>10}")
    print("─" * len(header))

    measurable = [r for r in rows if r["hybrid"]["precision@5"] >= 0]
    if measurable:
        avg_b = sum(r["bm25"]["precision@5"] for r in measurable) / len(measurable)
        avg_v = sum(r["vector"]["precision@5"] for r in measurable) / len(measurable)
        avg_h = sum(r["hybrid"]["precision@5"] for r in measurable) / len(measurable)
        print(f"{'avg':<46}  {avg_b:>8.2f}  {avg_v:>8.2f}  {avg_h:>10.2f}")
    print()


def main() -> None:
    queries = json.loads(QUERIES_PATH.read_text())
    RESULTS_DIR.mkdir(exist_ok=True)

    results = []
    for i, q in enumerate(queries, 1):
        print(f"[{i:>2}/{len(queries)}] {q['query'][:60]}")
        t0 = time.time()
        try:
            row = run_query(q)
        except Exception as exc:
            print(f"       ERROR: {exc}")
            row = {"id": q["id"], "query": q["query"], "error": str(exc)}
        elapsed = time.time() - t0
        print(f"       hybrid={row.get('hybrid', {}).get('result_count', '?')} results  ({elapsed:.1f}s)")
        results.append(row)

    print_summary([r for r in results if "error" not in r])

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = RESULTS_DIR / f"report_{ts}.json"
    out_path.write_text(json.dumps(results, indent=2, default=str))
    print(f"Report saved → {out_path}")


if __name__ == "__main__":
    main()
