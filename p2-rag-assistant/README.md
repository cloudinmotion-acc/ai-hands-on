# P2 — RAG Assistant

Chat with your documents. Upload PDFs, Excel files, or text — the system chunks, embeds, and stores them in pgvector, then answers questions with citations.

## What it does

Ingest documents → chunk + embed → store in pgvector → ask questions → LLM answers with source citations pulled from the vector store.

## Stack

- FastAPI backend + Next.js frontend
- pgvector (PostgreSQL) for vector storage
- NVIDIA NIM embeddings + LLM
- Docker for the database

## Prerequisites

PostgreSQL with pgvector running on port 5432.

```bash
# Quick start with Docker
docker run -d \
  --name pgvector \
  -e POSTGRES_USER=admin \
  -e POSTGRES_PASSWORD=yourpassword \
  -e POSTGRES_DB=p2_rag \
  -p 5432:5432 \
  pgvector/pgvector:pg16
```

## Setup

```bash
# Backend
cd p2-rag-assistant/backend
pip install -r requirements.txt
cp .env.example .env        # fill in NVIDIA_API_KEY and DB credentials

# Frontend
cd p2-rag-assistant/frontend
npm install
```

**backend/.env**
```
NVIDIA_API_KEY=nvapi-your-key-here
NVIDIA_BASE_URL=https://integrate.api.nvidia.com/v1
DB_USER=admin
DB_PASSWORD=yourpassword
DB_HOST=localhost
DB_PORT=5432
DB_NAME=p2_rag
```

## Run

```bash
# Terminal 1 — backend (from backend/)
uvicorn main:app --port 8000

# Terminal 2 — frontend (from frontend/)
npm run dev
```

Open `http://localhost:3000`.

## First use

1. Click **Upload** and ingest at least one document
2. Wait for the "ingested" confirmation
3. Type a question in the chat

## Key endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/ingest` | Upload and chunk a document |
| POST | `/query` | Ask a question, get answer + citations |
| GET | `/sources` | List all ingested documents |
| DELETE | `/sources` | Remove all documents |
| GET | `/health` | Check backend is running |

## Project structure

```
p2-rag-assistant/
  backend/
    main.py       ← FastAPI app, /ingest + /query endpoints
    db.py         ← pgvector connection + schema
    ingest.py     ← chunking + embedding pipeline
    query.py      ← retrieval + LLM answer generation
    requirements.txt
    .env.example
  frontend/
    app/          ← Next.js app router
    next.config.ts ← proxies /api/* to backend :8000
```
