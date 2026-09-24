"""
P5 Ingest — products.xlsx → Postgres (structured) + pgvector (embeddings)

What this does:
  1. Connects to Postgres, enables pgvector extension
  2. Creates the `products` table (drops and recreates for a clean re-run)
  3. Inserts all 65 rows from products.xlsx
  4. Embeds each product description via NVIDIA NIM
  5. Stores the embedding vector in the same row

Run from backend/:
    python -m ingest.load_products
"""

import os
import sys
import json
from pathlib import Path

import httpx
import pandas as pd
import psycopg2
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv(Path(__file__).parent.parent / ".env")

sys.path.insert(0, str(Path(__file__).parent.parent))
from db import get_db_url
DB_URL = get_db_url()
API_KEY   = os.environ["NVIDIA_API_KEY"]
BASE_URL  = os.environ.get("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1")
EMBED_MODEL = os.environ.get("EMBED_MODEL", "nvidia/nv-embedqa-e5-v5")
EMBED_DIM   = int(os.environ.get("EMBED_DIM", "2048"))
XLSX_PATH   = Path(__file__).parent.parent / "data" / "products.xlsx"
BATCH_SIZE  = 20   # embed this many descriptions per API call


# ── Postgres helpers ──────────────────────────────────────────────────────────

DDL = f"""
CREATE EXTENSION IF NOT EXISTS vector;

DROP TABLE IF EXISTS products;

CREATE TABLE products (
    id          INTEGER PRIMARY KEY,
    name        TEXT    NOT NULL,
    category    TEXT,
    gender      TEXT,
    colour      TEXT,
    size        TEXT,
    min_age     INTEGER,
    max_age     INTEGER,
    price       INTEGER,
    fabric      TEXT,
    in_stock    BOOLEAN,
    description TEXT,
    embedding   vector({EMBED_DIM})
);
"""

INSERT_SQL = """
INSERT INTO products
    (id, name, category, gender, colour, size, min_age, max_age,
     price, fabric, in_stock, description)
VALUES
    (%(id)s, %(name)s, %(category)s, %(gender)s, %(colour)s, %(size)s,
     %(min_age)s, %(max_age)s, %(price)s, %(fabric)s, %(in_stock)s, %(description)s)
"""

UPDATE_EMBED_SQL = """
UPDATE products SET embedding = %s::vector WHERE id = %s
"""


def create_table(conn) -> None:
    with conn.cursor() as cur:
        cur.execute(DDL)
    conn.commit()
    print("Table created.")


def insert_rows(conn, df: pd.DataFrame) -> None:
    records = df.to_dict(orient="records")
    with conn.cursor() as cur:
        cur.executemany(INSERT_SQL, records)
    conn.commit()
    print(f"Inserted {len(records)} rows.")


# ── Embedding ─────────────────────────────────────────────────────────────────

def embed_texts(texts: list[str], client: OpenAI) -> list[list[float]]:
    """Call NVIDIA NIM embedding endpoint; returns list of float vectors."""
    response = client.embeddings.create(
        model=EMBED_MODEL,
        input=texts,
        encoding_format="float",
        extra_body={"input_type": "passage", "truncate": "END"},
    )
    # sort by index to match input order
    sorted_data = sorted(response.data, key=lambda d: d.index)
    return [item.embedding for item in sorted_data]


def update_embeddings(conn, df: pd.DataFrame, client: OpenAI) -> None:
    ids   = df["id"].tolist()
    texts = df["description"].tolist()
    total = len(texts)

    all_embeddings: list[list[float]] = []

    for start in range(0, total, BATCH_SIZE):
        batch_texts = texts[start : start + BATCH_SIZE]
        batch_ids   = ids[start : start + BATCH_SIZE]
        print(f"  Embedding rows {start + 1}–{min(start + BATCH_SIZE, total)} / {total}…")
        vecs = embed_texts(batch_texts, client)
        all_embeddings.extend(vecs)

    # write to Postgres
    with conn.cursor() as cur:
        for pid, vec in zip(ids, all_embeddings):
            vec_str = "[" + ",".join(f"{v:.8f}" for v in vec) + "]"
            cur.execute(UPDATE_EMBED_SQL, (vec_str, pid))

    conn.commit()
    print(f"Embeddings stored for {total} products.")


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    # Load data
    if not XLSX_PATH.exists():
        sys.exit(f"products.xlsx not found at {XLSX_PATH}. Run generate_products.py first.")

    df = pd.read_excel(XLSX_PATH)
    print(f"Loaded {len(df)} products from {XLSX_PATH.name}.")

    # Postgres
    conn = psycopg2.connect(DB_URL)
    print("Connected to Postgres.")

    create_table(conn)
    insert_rows(conn, df)

    # NVIDIA embeddings
    embed_client = OpenAI(
        api_key=API_KEY,
        base_url=BASE_URL,
        http_client=httpx.Client(verify=False),
    )

    print(f"Embedding descriptions with {EMBED_MODEL}…")
    update_embeddings(conn, df, embed_client)

    conn.close()
    print("\nDone. All products are in Postgres with embeddings.")

    # Quick sanity check
    conn2 = psycopg2.connect(DB_URL)
    with conn2.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM products WHERE embedding IS NOT NULL")
        count = cur.fetchone()[0]
    conn2.close()
    print(f"Sanity check: {count} / {len(df)} rows have embeddings.")


if __name__ == "__main__":
    main()
