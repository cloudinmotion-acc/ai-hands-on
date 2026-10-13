"""
Propagation evaluator: verifies that a HITL edit in scoping propagates forward into HLD.

Process:
  1. Create a new P7 session for the test requirement
  2. Run scoping (auto-approve as normal)
  3. When scoping completes, inject a specific constraint into the content
  4. Submit the edited content instead of plain approve
  5. Auto-approve solution
  6. When HLD completes, check if the injected keyword appears in HLD content
"""

import logging
import re

from runner import run_scenario, create_session

logger = logging.getLogger("p8.propagation")

TEST_REQUIREMENT = (
    "Build a LinkedIn post scheduling assistant that lets content creators write post "
    "drafts, schedule them for optimal engagement times, and get AI-suggested reactions. "
    "It should support multiple social accounts and provide analytics on post performance."
)

INJECTION_TEXT = (
    "\n\nADDITIONAL CONSTRAINT: The system must support full offline mode. "
    "Users should be able to draft and queue posts without internet connectivity, "
    "with local data sync when the connection is restored. This is a hard requirement."
)

SEARCH_TERM = "offline"
EDIT_STAGE = "scoping"
CHECK_STAGE = "hld"


async def evaluate(*, p7_url: str, timeout: int = 400) -> dict:
    """
    Run the propagation test. Returns:
        {
            "pass": bool,
            "scenario": str,
            "edit_stage": "scoping",
            "check_stage": "hld",
            "injected": str,
            "search_term": str,
            "found": bool,
            "evidence": str,
            "error": str | None
        }
    """
    logger.info("Propagation test: creating session")
    try:
        session_id = await create_session(p7_url=p7_url)
        logger.info(f"Propagation session: {session_id[:8]}")

        result = await run_scenario(
            requirement=TEST_REQUIREMENT,
            p7_url=p7_url,
            session_id=session_id,
            edit_at={"stage": EDIT_STAGE, "inject": INJECTION_TEXT},
            timeout=timeout,
        )

        if result.get("error"):
            return {
                "pass": False,
                "scenario": TEST_REQUIREMENT[:80] + "...",
                "edit_stage": EDIT_STAGE,
                "check_stage": CHECK_STAGE,
                "injected": INJECTION_TEXT.strip(),
                "search_term": SEARCH_TERM,
                "found": False,
                "evidence": "",
                "error": result["error"],
            }

        hld_content = result["outputs"].get(CHECK_STAGE, "")
        found = SEARCH_TERM.lower() in hld_content.lower()

        # Find the specific line/bullet containing the search term as evidence.
        # Split by newlines; skip headings, separator lines, and header rows.
        evidence = ""
        if found:
            for line in hld_content.split("\n"):
                line = line.strip()
                if SEARCH_TERM.lower() not in line.lower():
                    continue
                if len(line) < 15:
                    continue
                # Skip markdown headings (## Title)
                if re.match(r"^#+\s", line):
                    continue
                # Skip table separator lines (---|---|---)
                if re.match(r"^[\|\-\s]+$", line):
                    continue
                # Skip table header rows (first cell is a generic label like "Component")
                if re.match(r"^\|?\s*(component|service|name|type|technology|interface|feature|module)\s*\|", line, re.I):
                    continue
                evidence = line[:250]
                break

        logger.info(f"Propagation test: found={found}, evidence_len={len(evidence)}")
        return {
            "pass": found,
            "scenario": TEST_REQUIREMENT[:80] + "...",
            "edit_stage": EDIT_STAGE,
            "check_stage": CHECK_STAGE,
            "injected": INJECTION_TEXT.strip(),
            "search_term": SEARCH_TERM,
            "found": found,
            "evidence": evidence,
            "error": None,
        }

    except Exception as exc:
        logger.error(f"Propagation test failed: {exc}", exc_info=True)
        return {
            "pass": False,
            "scenario": TEST_REQUIREMENT[:80] + "...",
            "edit_stage": EDIT_STAGE,
            "check_stage": CHECK_STAGE,
            "injected": INJECTION_TEXT.strip(),
            "search_term": SEARCH_TERM,
            "found": False,
            "evidence": "",
            "error": str(exc),
        }
