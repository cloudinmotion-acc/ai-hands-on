"""
Input guard orchestrator — runs all three checks in order.

Order matters:
  1. injection_detector  — cheapest (no LLM), blocks immediately if triggered
  2. pii_detector        — LLM call, rewrites text so downstream sees clean input
  3. topic_filter        — LLM call, blocks if off-topic

If injection fires → stop, return block (never reach PII or topic checks).
If PII fires → rewrite text, continue to topic check with scrubbed version.
If topic fires → block.
"""

from langsmith import traceable

from . import injection_detector, pii_detector, topic_filter
from .types import GuardResult


@traceable(name="input_guard", run_type="chain")
def check(text: str) -> GuardResult:
    # ── 1. Injection check ────────────────────────────────────────────
    result = injection_detector.check(text)
    result.guard_name = "injection_detector"
    if not result.passed:
        return result

    # ── 2. PII check (rewrite, never block) ──────────────────────────
    pii_result = pii_detector.check(text)
    pii_result.guard_name = "pii_detector"

    if pii_result.action == "rewrite":
        # Use scrubbed text for all subsequent checks
        text = pii_result.modified_text

    # ── 3. Topic check ────────────────────────────────────────────────
    topic_result = topic_filter.check(text)
    topic_result.guard_name = "topic_filter"

    if not topic_result.passed:
        return topic_result

    # ── All passed — return the (possibly scrubbed) clean text ────────
    if pii_result.action == "rewrite":
        # Bubble up the PII rewrite so main.py knows to use modified_text
        return pii_result

    return GuardResult(passed=True, action="allow", reason="all input guards passed")
