"""
P6 guard eval — runs all adversarial queries through the input guard
and checks the result against expected_action.

Run from p6-hardened-search/backend/:
    python ../eval/run_eval.py
"""

import json
import sys
from pathlib import Path

# Make guards importable from backend/
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / "backend" / ".env")

from guards import input_guard  # noqa: E402

QUERIES_FILE = Path(__file__).parent / "adversarial_queries.json"

# ── colour codes ──────────────────────────────────────────────────────
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
RESET  = "\033[0m"
BOLD   = "\033[1m"


def run_eval():
    queries = json.loads(QUERIES_FILE.read_text())

    results = []
    passed = 0

    print(f"\n{BOLD}P6 Input Guard Eval — {len(queries)} queries{RESET}\n")
    print(f"{'ID':<4} {'Category':<12} {'Expected':<10} {'Got':<10} {'Status':<8} Reason")
    print("─" * 80)

    for q in queries:
        result = input_guard.check(q["query"])
        got    = result.action
        want   = q["expected_action"]
        ok     = got == want

        if ok:
            passed += 1
            status = f"{GREEN}PASS{RESET}"
        else:
            status = f"{RED}FAIL{RESET}"

        # Truncate reason for display
        reason = result.reason[:55] + "…" if len(result.reason) > 55 else result.reason

        print(f"{q['id']:<4} {q['category']:<12} {want:<10} {got:<10} {status:<18} {reason}")
        results.append({**q, "got": got, "passed": ok, "reason": result.reason})

    print("─" * 80)
    total = len(queries)
    colour = GREEN if passed == total else (YELLOW if passed >= total * 0.8 else RED)
    print(f"\n{colour}{BOLD}Result: {passed}/{total} passed ({passed/total*100:.0f}%){RESET}\n")

    # Show failures in detail
    failures = [r for r in results if not r["passed"]]
    if failures:
        print(f"{RED}Failures:{RESET}")
        for f in failures:
            print(f"  ID {f['id']} [{f['category']}]: expected={f['expected_action']} got={f['got']}")
            print(f"    Query  : {f['query'][:80]}")
            print(f"    Reason : {f['reason']}")
            print()

    return passed == total


if __name__ == "__main__":
    success = run_eval()
    sys.exit(0 if success else 1)
