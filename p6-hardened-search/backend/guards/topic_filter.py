"""
Topic filter — checks if the query is relevant to clothing/fashion/shopping.

Fast path: obvious shopping keywords → allow immediately (no LLM cost).
LLM path: for anything ambiguous.

Greetings and meta-questions ("what can you help with?") are allowed —
they're harmless and the P5 agent handles them gracefully.
"""

import json
import os

import httpx
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langsmith import traceable

from .types import GuardResult

load_dotenv()

# ── fast-path keywords ────────────────────────────────────────────────
# Any query containing these is obviously on-topic — skip the LLM call.
_SHOPPING_KEYWORDS = {
    "dress", "shirt", "pants", "jeans", "jacket", "kurta", "saree", "lehenga",
    "top", "skirt", "blouse", "hoodie", "shorts", "suit", "coat", "shoes",
    "cotton", "silk", "denim", "linen", "fleece", "georgette", "chiffon",
    "buy", "shop", "wear", "outfit", "clothes", "clothing", "fashion",
    "size", "price", "colour", "color", "fabric", "style", "in stock",
    "under", "₹", "rupees", "women", "men", "boys", "girls", "kids",
}

_SYSTEM_PROMPT = """You are a content classifier for a retail clothing chatbot.
Decide if the user message is relevant to this chatbot's purpose.

RELEVANT (return true):
- Clothing, fashion, or shopping queries
- Product questions (sizes, colours, fabrics, prices)
- Greetings, thanks, or meta questions ("what can you do?")

NOT RELEVANT (return false):
- Completely unrelated topics: history, science, cooking, travel, coding, etc.
- Requests to do harmful or illegal things

Return ONLY valid JSON, no explanation:
{"is_relevant": true/false, "reason": "one short sentence"}"""


# ── fast path ─────────────────────────────────────────────────────────

def _fast_path(text: str) -> bool | None:
    """Return True if obviously on-topic, None if ambiguous (needs LLM)."""
    lowered = text.lower()
    if any(kw in lowered for kw in _SHOPPING_KEYWORDS):
        return True
    # very short inputs (greetings, "hi", "thanks") → allow without LLM
    if len(text.strip().split()) <= 3:
        return True
    return None


# ── LLM check ─────────────────────────────────────────────────────────

def _llm_check(text: str) -> GuardResult:
    llm = ChatOpenAI(
        model=os.environ["AGENT_MODEL"],
        base_url=os.environ["NVIDIA_BASE_URL"],
        api_key=os.environ["NVIDIA_API_KEY"],
        temperature=0,
        http_client=httpx.Client(verify=False),
        http_async_client=httpx.AsyncClient(verify=False),
    )

    response = llm.invoke([
        SystemMessage(content=_SYSTEM_PROMPT),
        HumanMessage(content=text),
    ])

    raw = response.content.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1].lstrip("json").strip()

    parsed = json.loads(raw)

    if parsed["is_relevant"]:
        return GuardResult(passed=True, action="allow", reason="on-topic")

    return GuardResult(
        passed=False,
        action="block",
        reason=f"off-topic: {parsed['reason']}",
    )


# ── main check ────────────────────────────────────────────────────────

@traceable(name="topic_filter", run_type="chain")
def check(text: str) -> GuardResult:
    fast = _fast_path(text)
    if fast is True:
        return GuardResult(passed=True, action="allow", reason="on-topic (fast path)")

    try:
        return _llm_check(text)
    except Exception as exc:
        # LLM failed → fail open (allow) so we don't block real users
        return GuardResult(
            passed=True,
            action="allow",
            reason=f"topic filter LLM failed ({type(exc).__name__}), defaulting to allow",
        )
