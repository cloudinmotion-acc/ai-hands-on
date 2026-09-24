"""
Query decomposer for P5.

Sends the raw user query to the LLM and asks it to split it into:
  - semantic_query : free-text description for vector + BM25 search
  - filters        : structured key-value pairs for sql_filter.py

The LLM always returns valid JSON. If it fails or the JSON is malformed,
we fall back to treating the whole query as the semantic_query with no filters.

Example input : "white cotton dress for girls under 500 rupees, in stock"
Example output:
  {
    "semantic_query": "white cotton dress for girls",
    "filters": {
      "colour": "white",
      "fabric": "cotton",
      "category": "kids",
      "gender": "girls",
      "max_price": 500,
      "in_stock": true
    }
  }
"""

import json
import os
from pathlib import Path

import httpx
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

load_dotenv(Path(__file__).parent.parent / ".env")

_AGENT_MODEL = os.environ.get("AGENT_MODEL", "nvidia/nemotron-3-super-120b-a12b")
_BASE_URL    = os.environ.get("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1")
_API_KEY     = os.environ["NVIDIA_API_KEY"]

_SYSTEM_PROMPT = """You are a query parser for a clothing search engine.

Given a user query, extract:
1. semantic_query — a clean natural-language description for semantic search (keep colours, fabrics, style words, item type)
2. filters — a JSON object with ONLY the keys that are explicitly mentioned:
   - gender    : one of ["boys", "girls", "unisex", "women", "men"]
   - colour    : lowercase colour name (e.g. "white", "blue", "black")
   - fabric    : lowercase fabric name (e.g. "cotton", "denim", "silk", "fleece", "linen")
   - min_age   : integer (years) — only if a specific age is mentioned
   - max_age   : integer (years) — only if a specific age is mentioned
   - max_price : integer (INR/₹) — only if a price limit is mentioned
   - in_stock  : true — only if user explicitly asks for available/in-stock items

Rules:
- Only include a filter key if the user explicitly stated it — never guess.
- "for girls" → gender = "girls"; "for boys" → gender = "boys"; "for women" → gender = "women"; "for men" → gender = "men"
- "for kids" or "for children" or "for toddlers" → gender is unspecified; set max_age = 12 instead
- "for teens" or "for teenagers" → set min_age = 13, max_age = 17
- "under ₹X", "below X rupees", "less than X" → max_price = X
- "available" or "in stock" → in_stock = true
- Do NOT include a "category" key — it is not a valid filter.

Output ONLY valid JSON, no explanation, no markdown:
{"semantic_query": "...", "filters": {...}}"""


def decompose(query: str) -> dict:
    """
    Returns {"semantic_query": str, "filters": dict}.
    Never raises — falls back to {"semantic_query": query, "filters": {}} on error.
    """
    llm = ChatOpenAI(
        model=_AGENT_MODEL,
        base_url=_BASE_URL,
        api_key=_API_KEY,
        temperature=0,
        http_client=httpx.Client(verify=False),
        http_async_client=httpx.AsyncClient(verify=False),
    )

    messages = [
        SystemMessage(content=_SYSTEM_PROMPT),
        HumanMessage(content=query),
    ]

    try:
        response = llm.invoke(messages)
        raw = response.content.strip()
        # strip markdown code fences if the LLM wraps its JSON
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        parsed = json.loads(raw)
        return {
            "semantic_query": parsed.get("semantic_query", query),
            "filters": parsed.get("filters", {}),
        }
    except Exception:
        return {"semantic_query": query, "filters": {}}
