"""
Trajectory evaluator: checks that all 4 stages ran in the correct order.
"""

EXPECTED_ORDER = ["scoping", "solution", "hld", "lld"]


def evaluate(stages_completed: list[str], stage_order: list[str]) -> dict:
    """
    Returns:
        pass: bool - all 4 stages present and in the correct order
        score: float - fraction of expected stages completed (0.0 - 1.0)
        missing: list[str] - stages not completed
        order_correct: bool - stages ran in the expected sequence
        details: dict - per-stage presence
    """
    present = {s for s in stages_completed}
    missing = [s for s in EXPECTED_ORDER if s not in present]

    order_correct = True
    if stage_order:
        expected_positions = {s: i for i, s in enumerate(EXPECTED_ORDER)}
        actual_positions = [
            expected_positions[s]
            for s in stage_order
            if s in expected_positions
        ]
        order_correct = actual_positions == sorted(actual_positions)

    score = len(EXPECTED_ORDER) - len(missing)
    score_frac = score / len(EXPECTED_ORDER)

    return {
        "pass": len(missing) == 0 and order_correct,
        "score": round(score_frac, 3),
        "missing": missing,
        "order_correct": order_correct,
        "stages_completed": stages_completed,
        "details": {s: s in present for s in EXPECTED_ORDER},
    }
