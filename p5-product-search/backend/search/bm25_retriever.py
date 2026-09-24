"""
BM25 keyword retriever for P5.

Loads all product descriptions from Postgres at import time, builds a BM25
index, and exposes a search() function for keyword queries.

BM25 is great for exact/near-exact matches that embeddings miss — product
names, colour words, fabric types, size tokens.
"""

import os
import re
from pathlib import Path

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv
from rank_bm25 import BM25Okapi

load_dotenv(Path(__file__).parent.parent / ".env")

from db import get_db_url
DB_URL = get_db_url()


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def _load_products() -> tuple[list[dict], BM25Okapi]:
    conn = psycopg2.connect(DB_URL)
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT id, name, category, gender, colour, size, min_age,
                       max_age, price, fabric, in_stock, description
                FROM products
                ORDER BY id
                """
            )
            products = [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()

    # build corpus: concat name + description for richer keyword coverage
    corpus = [
        _tokenize(f"{p['name']} {p['description']}")
        for p in products
    ]
    index = BM25Okapi(corpus)
    return products, index


# Index is built once at module import — stays in memory for the process lifetime.
_PRODUCTS, _INDEX = _load_products()


def search(query: str, top_k: int = 10) -> list[dict]:
    """
    Returns up to top_k products ranked by BM25 score.
    Products with score 0 are excluded (no keyword overlap at all).
    Each result dict includes a 'bm25_score' key.
    """
    tokens = _tokenize(query)
    scores = _INDEX.get_scores(tokens)

    ranked = sorted(
        enumerate(scores), key=lambda x: x[1], reverse=True
    )

    results = []
    for idx, score in ranked[:top_k]:
        if score == 0:
            break
        row = dict(_PRODUCTS[idx])
        row["bm25_score"] = round(float(score), 4)
        results.append(row)

    return results


def reload() -> None:
    """Force re-load the index from Postgres (useful after re-ingest)."""
    global _PRODUCTS, _INDEX
    _PRODUCTS, _INDEX = _load_products()
