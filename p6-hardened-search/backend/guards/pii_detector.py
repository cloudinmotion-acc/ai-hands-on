"""
PII detector — LLM primary, regex fallback.

Action is always "rewrite" (never block) so the search still works.
The original text is never forwarded — only the scrubbed version is.
The reason field records what was found and which path ran, for LangSmith.
"""

import json
import os
import re

import httpx
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langsmith import traceable

from .types import GuardResult

load_dotenv()

# ── regex fallback patterns ────────────────────────────────────────────

_PATTERNS = {
    "email":       re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
    "phone_in":    re.compile(r"\b[6-9]\d{9}\b"),                         # Indian mobile
    "phone_intl":  re.compile(r"\b(\+?\d{1,3}[\s.-]?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}\b"),
    "credit_card": re.compile(r"\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b"),
    "aadhaar":     re.compile(r"\b\d{4}\s\d{4}\s\d{4}\b"),                # Indian national ID
}

_PLACEHOLDER = {
    "email":       "[EMAIL]",
    "phone_in":    "[PHONE]",
    "phone_intl":  "[PHONE]",
    "credit_card": "[CARD]",
    "aadhaar":     "[AADHAAR]",
}

_SYSTEM_PROMPT = """You are a PII detector for a retail shopping chatbot.
Identify and redact any personal information in the user message.

PII includes: full names, email addresses, phone numbers, home addresses,
credit/debit card numbers, national ID numbers (Aadhaar, PAN, SSN).

Return ONLY valid JSON, no explanation, no markdown:
{"has_pii": true/false, "pii_types": ["email", "phone", ...], "scrubbed_text": "..."}

Replace PII with tokens like [EMAIL], [PHONE], [NAME], [ADDRESS], [CARD].
If no PII found: {"has_pii": false, "pii_types": [], "scrubbed_text": "<original text unchanged>"}"""


# ── LLM check (primary) ───────────────────────────────────────────────

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

    if parsed["has_pii"]:
        return GuardResult(
            passed=True,
            action="rewrite",
            reason=f"PII detected (LLM): {', '.join(parsed['pii_types'])}",
            modified_text=parsed["scrubbed_text"],
        )

    return GuardResult(passed=True, action="allow", reason="clean")


# ── regex fallback ────────────────────────────────────────────────────

def _regex_check(text: str) -> GuardResult:
    found_types = []
    scrubbed = text

    for label, pattern in _PATTERNS.items():
        if pattern.search(scrubbed):
            found_types.append(label)
            scrubbed = pattern.sub(_PLACEHOLDER[label], scrubbed)

    if found_types:
        return GuardResult(
            passed=True,
            action="rewrite",
            reason=f"PII detected (regex fallback): {', '.join(found_types)}",
            modified_text=scrubbed,
        )

    return GuardResult(passed=True, action="allow", reason="clean")


# ── main check (LLM → regex on failure) ──────────────────────────────

@traceable(name="pii_detector", run_type="chain")
def check(text: str) -> GuardResult:
    try:
        return _llm_check(text)
    except Exception as exc:
        result = _regex_check(text)
        result.reason += f" [LLM failed: {type(exc).__name__}]"
        return result
