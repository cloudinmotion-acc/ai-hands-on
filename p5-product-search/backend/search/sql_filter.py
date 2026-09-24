"""
SQL filter retriever for P5.

Takes a structured filter dict (from the decomposer) and returns matching
product rows directly from Postgres — no embeddings needed.

Filter keys (all optional):
    category  : str   — "kids", "teens", "women", "men"
    gender    : str   — "boys", "girls", "unisex", "women", "men"
    colour    : str   — e.g. "white", "blue"
    fabric    : str   — e.g. "cotton", "denim"
    min_age   : int   — minimum age in years
    max_age   : int   — maximum age in years
    max_price : int   — upper price bound (INR)
    in_stock  : bool  — True to restrict to in-stock only
"""

import os
from typing import Any

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(Path(__file__).parent.parent / ".env")

from db import get_db_url
DB_URL = get_db_url()


def search(filters: dict[str, Any], top_k: int = 20) -> list[dict]:
    """
    Run a parametric SQL query based on filters.
    Returns list of product dicts ordered by price ASC, capped at top_k.
    Empty filters → returns all products (up to top_k).
    """
    conditions: list[str] = []
    params: list[Any] = []

    if cat := filters.get("category"):
        conditions.append("LOWER(category) = LOWER(%s)")
        params.append(cat)

    if gen := filters.get("gender"):
        conditions.append("LOWER(gender) = LOWER(%s)")
        params.append(gen)

    if col := filters.get("colour"):
        conditions.append("LOWER(colour) = LOWER(%s)")
        params.append(col)

    if fab := filters.get("fabric"):
        conditions.append("LOWER(fabric) = LOWER(%s)")
        params.append(fab)

    if (mn := filters.get("min_age")) is not None:
        # product's age range must overlap the requested minimum age
        conditions.append("max_age >= %s")
        params.append(int(mn))

    if (mx := filters.get("max_age")) is not None:
        # product's age range must overlap the requested maximum age
        conditions.append("min_age <= %s")
        params.append(int(mx))

    if (mp := filters.get("max_price")) is not None:
        conditions.append("price <= %s")
        params.append(int(mp))

    if filters.get("in_stock") is True:
        conditions.append("in_stock = TRUE")

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    sql = f"""
        SELECT id, name, category, gender, colour, size, min_age, max_age,
               price, fabric, in_stock, description
        FROM products
        {where}
        ORDER BY price ASC
        LIMIT %s
    """
    params.append(top_k)

    conn = psycopg2.connect(DB_URL)
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()
