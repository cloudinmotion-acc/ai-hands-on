"""
pgvector cosine-similarity retriever for P5.

Embeds the query with NVIDIA NIM, then does a nearest-neighbour search
against the `embedding` column in the `products` table.

This is the semantic leg of the hybrid pipeline — it finds products that
*mean* the same thing even when keywords don't match exactly (e.g. "warm
winter jacket" → finds "padded fleece coat").
"""

import os
from pathlib import Path

import httpx
import psycopg2
import psycopg2.extras
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv(Path(__file__).parent.parent / ".env")

from db import get_db_url
DB_URL      = get_db_url()
API_KEY     = os.environ["NVIDIA_API_KEY"]
BASE_URL    = os.environ.get("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1")
EMBED_MODEL = os.environ.get("EMBED_MODEL", "nvidia/nv-embedqa-e5-v5")
EMBED_DIM   = int(os.environ.get("EMBED_DIM", "1024"))


def _embed_client() -> OpenAI:
    return OpenAI(
        api_key=API_KEY,
        base_url=BASE_URL,
        http_client=httpx.Client(verify=False),
    )


def _embed_query(text: str) -> list[float]:
    client = _embed_client()
    resp = client.embeddings.create(
        model=EMBED_MODEL,
        input=[text],
        encoding_format="float",
        extra_body={"input_type": "query", "truncate": "END"},
    )
    return resp.data[0].embedding


_COSINE_SQL = """
SELECT id, name, category, gender, colour, size, min_age, max_age,
       price, fabric, in_stock, description,
       1 - (embedding <=> %s::vector) AS similarity
FROM products
WHERE embedding IS NOT NULL
ORDER BY embedding <=> %s::vector
LIMIT %s
"""


def search(query: str, top_k: int = 10) -> list[dict]:
    """
    Embed query, run pgvector cosine-similarity search, return top_k results.
    Each result dict includes a 'similarity' key (0–1, higher = more similar).
    """
    vec = _embed_query(query)
    vec_str = "[" + ",".join(f"{v:.8f}" for v in vec) + "]"

    conn = psycopg2.connect(DB_URL)
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(_COSINE_SQL, (vec_str, vec_str, top_k))
            rows = cur.fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()
