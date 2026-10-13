"""
P8 FastAPI backend  -  Eval Harness API.

Endpoints:
  GET  /health              → liveness check
  GET  /results             → serve latest.json (or 404 if no run yet)
  POST /eval/run            → SSE: run full evaluation pipeline
"""

import asyncio
import json
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from engine import EvalConfig, run_eval

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)-5s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("p8")

SSE_HEADERS = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}


def _sse(data: dict) -> str:
    return f"data: {json.dumps(data)}\n\n"


def _make_config(quick: bool = False, skip_propagation: bool = False) -> EvalConfig:
    return EvalConfig(
        p7_url=os.environ.get("P7_URL", "http://localhost:8000"),
        scenarios_file=os.environ.get("SCENARIOS_FILE", "scenarios/requirements.json"),
        checklists_dir=os.environ.get("CHECKLISTS_DIR", "checklists"),
        results_dir=os.environ.get("RESULTS_DIR", "../results"),
        judge_model=os.environ.get("JUDGE_MODEL", "nvidia/nemotron-3-super-120b-a12b"),
        nvidia_api_key=os.environ.get("NVIDIA_API_KEY", ""),
        nvidia_base_url=os.environ.get("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1"),
        concurrency=int(os.environ.get("CONCURRENCY", "3")),
        quick=quick,
        skip_propagation=skip_propagation,
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("P8 Eval API ready")
    yield


app = FastAPI(title="P8 Eval Harness", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class RunRequest(BaseModel):
    quick: bool = False
    skip_propagation: bool = False


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/results")
async def get_results():
    config = _make_config()
    latest = Path(config.results_dir) / "latest.json"
    if not latest.exists():
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="No eval results yet. Run an evaluation first.")
    return json.loads(latest.read_text(encoding="utf-8"))


@app.post("/eval/run")
async def run_eval_endpoint(req: RunRequest) -> StreamingResponse:
    config = _make_config(quick=req.quick, skip_propagation=req.skip_propagation)
    logger.info(f"Eval run started: quick={req.quick}, skip_propagation={req.skip_propagation}")

    async def _stream():
        queue: asyncio.Queue = asyncio.Queue()

        async def _emit(event: dict):
            await queue.put(event)

        async def _producer():
            try:
                await run_eval(config, _emit)
            finally:
                await queue.put(None)

        producer_task = asyncio.create_task(_producer())

        while True:
            item = await queue.get()
            if item is None:
                break
            yield _sse(item)

        await producer_task

    return StreamingResponse(
        _stream(),
        media_type="text/event-stream",
        headers=SSE_HEADERS,
    )
