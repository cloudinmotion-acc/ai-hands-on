# P5 — Hybrid Product Search

Three-retriever search pipeline (SQL + BM25 + pgvector) fused with RRF, exposed as an MCP tool, driven by a LangGraph agent, with mismatch highlighting in the UI.

## What it does

User query → LLM decomposer splits it into structured filters + semantic text → SQL filter, BM25 keyword search, and pgvector semantic search run in parallel → RRF merges the three ranked lists → post-RRF hard filter enforces gender/in_stock → LangGraph agent streams the answer → UI shows product cards with amber badges for attribute mismatches.

## Stack

- FastAPI backend + Next.js frontend (port 3001)
- pgvector (PostgreSQL) — product embeddings
- BM25 (`rank_bm25`) — in-memory keyword index
- NVIDIA NIM — embeddings (`nv-embedqa-e5-v5`, 2048-dim) + LLM (`nemotron-3-super-120b-a12b`)
- FastMCP — wraps pipeline as a single tool
- LangGraph — ReAct agent with 4-attempt backoff

## Prerequisites

PostgreSQL with pgvector on port 5432.

```bash
docker run -d \
  --name pgvector-p5 \
  -e POSTGRES_USER=admin \
  -e POSTGRES_PASSWORD=yourpassword \
  -e POSTGRES_DB=p5_rag \
  -p 5432:5432 \
  pgvector/pgvector:pg16
```

## Setup

```bash
# Backend
cd p5-product-search/backend
pip install -r requirements.txt
cp .env.example .env        # fill in NVIDIA_API_KEY and DB credentials

# Frontend
cd p5-product-search/frontend
npm install
```

**backend/.env**
```
NVIDIA_API_KEY=nvapi-your-key-here
NVIDIA_BASE_URL=https://integrate.api.nvidia.com/v1
EMBED_MODEL=nvidia/nv-embedqa-e5-v5
AGENT_MODEL=nvidia/nemotron-3-super-120b-a12b
DB_USER=admin
DB_PASSWORD=yourpassword
DB_HOST=localhost
DB_PORT=5432
DB_NAME=p5_rag
EMBED_DIM=2048
```

## First-time ingest

Run once to populate the product catalogue and build embeddings:

```bash
cd p5-product-search/backend
python ingest/ingest.py
```

## Run

```bash
# Terminal 1 — backend (from backend/)
uvicorn main:app --port 8000

# Terminal 2 — frontend (from frontend/)
npm run dev          # starts on port 3001
```

Open `http://localhost:3001`.

## Eval

```bash
# From p5-product-search/
python eval/run_eval.py
```

Runs 15 queries across BM25-only, vector-only, and hybrid modes. Reports Precision@5 per mode.

## MCP server (optional)

The full pipeline is also available as a standalone MCP tool:

```bash
cd p5-product-search/backend
python mcp_server.py            # stdio transport
python mcp_server.py --http     # HTTP on port 8001
```

## Project structure

```
p5-product-search/
  backend/
    main.py             ← FastAPI + SSE streaming
    agent.py            ← LangGraph ReAct agent
    mcp_server.py       ← FastMCP tool (search_products)
    search/
      decomposer.py     ← LLM query → {semantic_query, filters}
      sql_filter.py     ← SQL WHERE clause from filters
      bm25_retriever.py ← BM25Okapi keyword search
      vector_retriever.py ← pgvector cosine similarity
      merger.py         ← RRF fusion (1/(60 + rank))
    ingest/             ← one-time product catalogue + embedding pipeline
    requirements.txt
    .env.example
  frontend/
    app/page.tsx        ← UI with mismatch badge highlighting
  eval/
    run_eval.py         ← Precision@5 evaluation
    queries.json        ← 15 test queries with expected product IDs
```
