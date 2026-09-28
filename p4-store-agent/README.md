# P4 — Store Agent

A LangGraph ReAct agent for retail store operations. Given a natural language request, it autonomously calls the right tools (stock check, order pricing, delivery ETA) and streams its reasoning to the UI.

## What it does

User sends a message → LangGraph ReAct loop decides which tools to call → streams `thinking`, `tool_call`, `tool_result`, `final_answer` events → UI renders the agent trace in real time.

Built-in tools:
- `check_stock(product_id)` — inventory lookup
- `price_order(items)` — order total calculation
- `delivery_eta(location)` — estimated delivery time

## Stack

- FastAPI backend (LangGraph agent + SSE streaming)
- Next.js frontend
- NVIDIA NIM (`nemotron-3-super-120b-a12b`)
- No database — tools use in-memory data

## Setup

```bash
# Backend
cd p4-store-agent/backend
pip install -r requirements.txt
cp .env.example .env        # fill in NVIDIA_API_KEY

# Frontend
cd p4-store-agent/frontend
npm install
```

**backend/.env**
```
NVIDIA_API_KEY=nvapi-your-key-here
NVIDIA_BASE_URL=https://integrate.api.nvidia.com/v1
AGENT_MODEL=nvidia/nemotron-3-super-120b-a12b
```

## Run

```bash
# Terminal 1 — backend (from backend/)
uvicorn main:app --port 8001

# Terminal 2 — frontend (from frontend/)
npm run dev
```

Open `http://localhost:3000`.

## Try these

The backend ships with 5 demo scenarios (`GET /scenarios`). Or type freely:
- "Do we have 50 units of product SKU-123 in stock?"
- "What's the total for 3× SKU-001 and 2× SKU-007?"
- "When will an order reach Mumbai?"

## Key endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/chat` | Send a message, receive SSE agent trace |
| GET | `/scenarios` | List built-in demo scenarios |
| GET | `/health` | Check backend is running |

## Project structure

```
p4-store-agent/
  backend/
    main.py       ← FastAPI app + SSE streaming
    agent.py      ← LangGraph ReAct graph definition
    tools.py      ← check_stock, price_order, delivery_eta
    requirements.txt
    .env.example
  frontend/
    app/
      api/chat/      ← proxies to backend :8001
      api/scenarios/ ← proxies to backend :8001
```
