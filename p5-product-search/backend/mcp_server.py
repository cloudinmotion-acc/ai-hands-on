"""
P5 MCP server — exposes the full hybrid search pipeline as a single tool.

Tool: search_products(query, top_k=10)
  Pipeline:
    1. decomposer  → semantic_query + structured filters
    2. sql_filter  → exact SQL matches
    3. bm25        → keyword matches
    4. vector      → semantic matches
    5. merger      → RRF fusion

Run:
    python mcp_server.py          # stdio transport (default for MCP clients)
    python mcp_server.py --http   # HTTP transport on port 8001
"""

import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from fastmcp import FastMCP

load_dotenv(Path(__file__).parent / ".env")

# lazy import so the BM25 index loads only when the server actually starts
from search import decomposer, sql_filter, bm25_retriever, vector_retriever, merger

mcp = FastMCP(name="p5-product-search")


def _hard_filter(products: list[dict], filters: dict) -> list[dict]:
    """Keep only products that satisfy hard demographic/availability constraints.

    Unisex products satisfy any gender request — a unisex hoodie is a valid
    result for "fleece hoodie for men".
    """
    out = []
    gender_want  = str(filters.get("gender", "")).lower()
    stock_needed = filters.get("in_stock") is True
    for p in products:
        if gender_want:
            pg = p.get("gender", "").lower()
            if pg != gender_want and pg != "unisex":
                continue
        if stock_needed and not p.get("in_stock", False):
            continue
        out.append(p)
    return out


@mcp.tool()
def search_products(query: str, top_k: int = 10) -> str:
    """
    Search the product catalogue using a hybrid pipeline.

    Combines SQL filtering (structured attributes), BM25 keyword search,
    and pgvector semantic search, then merges results with RRF.

    Args:
        query:  Natural-language search query from the user.
                Example: "white cotton dress for girls under 500 rupees in stock"
        top_k:  Maximum number of products to return (default 10).

    Returns:
        JSON string with:
          - decomposed: { semantic_query, filters }
          - results: list of product dicts with rrf_score
    """
    # Step 1 — decompose
    decomposed = decomposer.decompose(query)
    sem_q   = decomposed["semantic_query"]
    filters = decomposed["filters"]

    # Step 2 — run all three retrievers.
    # Expand the pool when filters are present so post-filtering has headroom;
    # keep 2× otherwise to avoid diluting the RRF merge for open queries.
    pool_k         = top_k * 4 if filters else top_k * 2
    sql_results    = sql_filter.search(filters, top_k=pool_k)
    bm25_results   = bm25_retriever.search(sem_q, top_k=pool_k)
    vector_results = vector_retriever.search(sem_q, top_k=pool_k)

    # Step 3 — merge with RRF over the expanded pool
    merged = merger.merge(sql_results, bm25_results, vector_results, top_k=pool_k)

    # Step 4 — enforce hard demographic/availability filters post-RRF.
    # BM25/vector can surface items of the wrong gender; this gates them out.
    # Only gender and in_stock are hard gates — colour/fabric stay soft so
    # near-matches (e.g. georgette when user said cotton) can still surface.
    if filters:
        filtered = _hard_filter(merged, filters)
        # use the filtered list if it has enough results; fall back otherwise
        if len(filtered) >= max(1, top_k // 4):
            merged = filtered[:top_k]
        else:
            merged = merged[:top_k]
    else:
        merged = merged[:top_k]

    # Strip embedding vectors from output (huge, not useful to the agent)
    for row in merged:
        row.pop("embedding", None)
        # convert bool to Python bool for clean JSON
        if "in_stock" in row:
            row["in_stock"] = bool(row["in_stock"])

    return json.dumps(
        {"decomposed": decomposed, "results": merged},
        indent=2,
        default=str,
    )


if __name__ == "__main__":
    if "--http" in sys.argv:
        mcp.run(transport="http", host="0.0.0.0", port=8001)
    else:
        mcp.run(transport="stdio")
