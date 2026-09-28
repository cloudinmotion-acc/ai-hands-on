"""
LangSmith tracing setup for P6.

How it works:
  - Setting LANGCHAIN_TRACING_V2=true auto-traces every LangChain LLM call.
  - Guards decorated with @traceable (from langsmith) appear as child spans.
  - This module provides the configure() call + a request-level context manager
    so main.py can attach per-request metadata (query, guards fired, latency).

Call configure() once at app startup.
Use request_trace() as a context manager around each /search request.
"""

import os
import time
from contextlib import contextmanager

from dotenv import load_dotenv
from langsmith import Client, traceable  # noqa: F401 — re-exported for convenience

load_dotenv()


def configure() -> None:
    """Validate LangSmith env vars are present. Tracing is enabled via env vars."""
    required = ["LANGCHAIN_API_KEY", "LANGCHAIN_PROJECT"]
    missing = [k for k in required if not os.environ.get(k)]
    if missing:
        raise EnvironmentError(
            f"LangSmith not configured. Missing env vars: {', '.join(missing)}\n"
            "Add them to your .env file."
        )
    # LANGCHAIN_TRACING_V2=true enables auto-tracing for all LangChain calls.
    os.environ.setdefault("LANGCHAIN_TRACING_V2", "true")
    os.environ.setdefault("LANGCHAIN_ENDPOINT", "https://api.smith.langchain.com")


@contextmanager
def request_trace(query: str):
    """
    Context manager that times a full /search request and yields a metadata dict.
    Caller populates the dict as guards run; we log it at the end.

    Usage in main.py:
        with request_trace(query) as meta:
            meta["input_guard_action"] = result.action
            ...
    """
    meta = {"query": query, "start_time": time.time()}
    try:
        yield meta
    finally:
        meta["latency_ms"] = round((time.time() - meta.pop("start_time")) * 1000)
        # LangSmith auto-captures LangChain calls inside this block.
        # The meta dict is available for debugging but not automatically
        # pushed to LangSmith — attach it via @traceable metadata if needed.
