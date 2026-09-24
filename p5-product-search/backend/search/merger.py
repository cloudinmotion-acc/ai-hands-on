"""
RRF merger for P5.

Takes result lists from the three retrievers and combines them using
Reciprocal Rank Fusion (RRF), which sidesteps the need to calibrate scores
across different retrieval systems.

RRF formula per result:
    rrf_score = sum(1 / (k + rank_i))   for each list i that contains the item
    where k = 60 (standard constant from the original RRF paper)

The merged list is sorted by rrf_score descending and deduplicated by product id.
"""

from typing import Any


_K = 60  # RRF smoothing constant


def merge(
    *ranked_lists: list[dict[str, Any]],
    top_k: int = 10,
) -> list[dict[str, Any]]:
    """
    Merge arbitrarily many ranked result lists via RRF.

    Each list item must have an "id" key. Lists can be empty.
    Returns top_k unique products, each augmented with an "rrf_score" key.
    The first occurrence of a product in any list wins for all non-score fields.
    """
    rrf_scores: dict[int, float] = {}
    product_store: dict[int, dict[str, Any]] = {}

    for ranked in ranked_lists:
        for rank, product in enumerate(ranked, start=1):
            pid = product["id"]
            rrf_scores[pid] = rrf_scores.get(pid, 0.0) + 1.0 / (_K + rank)
            if pid not in product_store:
                product_store[pid] = product

    sorted_ids = sorted(rrf_scores, key=lambda pid: rrf_scores[pid], reverse=True)

    results = []
    for pid in sorted_ids[:top_k]:
        row = dict(product_store[pid])
        row["rrf_score"] = round(rrf_scores[pid], 6)
        results.append(row)

    return results
