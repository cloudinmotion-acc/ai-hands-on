"""
Output guard — runs on the P5 agent's final answer before it reaches the user.

Two checks in one LLM call (to keep latency low):
  1. Hallucination — does the answer claim things not supported by the search results?
  2. Tone          — is the response appropriate for a retail shopping chatbot?

If either check fails → action="rewrite", modified_text has the fixed version.
The original answer is never sent to the user in that case.
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

_SYSTEM_PROMPT = """You are a quality checker for a retail clothing chatbot's responses.

You will receive:
- PRODUCTS: the actual search results (name, price, fabric, stock status)
- ANSWER: what the chatbot said

Check for TWO things:

1. HALLUCINATION — does the answer make specific claims about products
   (prices, availability, fabrics, sizes) that contradict the search results?
   Minor phrasing differences are fine. Only flag factual contradictions.

2. TONE — is the answer appropriate? Flag if it is rude, dismissive,
   excessively apologetic (saying sorry 3+ times), or completely ignores
   what the user asked.

If both checks pass, return the answer unchanged.
If either fails, rewrite the answer to fix the issue.

Return ONLY valid JSON:
{
  "hallucination": true/false,
  "tone_ok": true/false,
  "issues": ["list of issues found, empty if none"],
  "final_answer": "the answer to send to the user (original if no issues, fixed if issues found)"
}"""


def _build_product_facts(tool_result: dict | None) -> str:
    """Format P5 tool_result products into a readable fact sheet."""
    if not tool_result:
        return "No products retrieved."

    products = tool_result.get("top_results", [])
    if not products:
        return "Search returned no products."

    lines = []
    for p in products[:10]:  # cap at 10 for prompt size
        stock = "In Stock" if p.get("in_stock") else "Out of Stock"
        lines.append(
            f"- {p.get('name', 'Unknown')} | ₹{p.get('price', '?')} | "
            f"{p.get('fabric', '?')} | {p.get('gender', '?')} | {stock}"
        )
    return "\n".join(lines)


@traceable(name="output_guard", run_type="chain")
def check(answer: str, tool_result: dict | None) -> GuardResult:
    product_facts = _build_product_facts(tool_result)

    user_message = f"""PRODUCTS:
{product_facts}

ANSWER:
{answer}"""

    llm = ChatOpenAI(
        model=os.environ["AGENT_MODEL"],
        base_url=os.environ["NVIDIA_BASE_URL"],
        api_key=os.environ["NVIDIA_API_KEY"],
        temperature=0,
        http_client=httpx.Client(verify=False),
        http_async_client=httpx.AsyncClient(verify=False),
    )

    try:
        response = llm.invoke([
            SystemMessage(content=_SYSTEM_PROMPT),
            HumanMessage(content=user_message),
        ])

        raw = response.content.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1].lstrip("json").strip()

        parsed = json.loads(raw)

        issues = parsed.get("issues", [])
        has_issue = parsed.get("hallucination") or not parsed.get("tone_ok", True)

        if has_issue:
            return GuardResult(
                passed=True,
                action="rewrite",
                reason=f"output guard rewrote: {'; '.join(issues)}",
                modified_text=parsed["final_answer"],
            )

        return GuardResult(passed=True, action="allow", reason="output guard passed")

    except Exception as exc:
        # LLM failed → pass through unchanged, log the failure
        return GuardResult(
            passed=True,
            action="allow",
            reason=f"output guard LLM failed ({type(exc).__name__}), passing through",
        )
