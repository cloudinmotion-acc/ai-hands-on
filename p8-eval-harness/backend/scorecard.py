"""
Scorecard: aggregates trajectory, completeness, and propagation results
into a single GO / NO-GO verdict with per-dimension pass/fail flags.
"""

from __future__ import annotations

THRESHOLDS = {
    "trajectory_rate": 13 / 15,
    "completeness_stage_min": 0.70,
    "propagation": True,
}

STAGE_NAMES = ["scoping", "solution", "hld", "lld"]


def build_scorecard(
    *,
    scenarios: list[dict],
    trajectory_results: list[dict],
    completeness_results: list[dict],
    propagation_result: dict,
    run_id: str,
    duration_s: float,
) -> dict:
    """
    Build the final evaluation scorecard.

    Args:
        scenarios: list of scenario dicts (id, title, requirement)
        trajectory_results: list of trajectory.evaluate() returns, one per scenario
        completeness_results: list of completeness.evaluate() returns, one per scenario
        propagation_result: propagation.evaluate() return
        run_id: ISO timestamp string
        duration_s: total eval wall time

    Returns:
        The full results dict (written to latest.json and returned to frontend)
    """
    # Trajectory aggregate
    passed_traj = sum(1 for r in trajectory_results if r["pass"])
    traj_rate = passed_traj / len(trajectory_results) if trajectory_results else 0.0
    traj_pass = traj_rate >= THRESHOLDS["trajectory_rate"]

    # Completeness aggregate (mean per stage across all scenarios)
    stage_means: dict[str, float] = {}
    for stage in STAGE_NAMES:
        stage_scores = [r.get(stage, 0.0) for r in completeness_results if r.get(stage) is not None]
        stage_means[stage] = round(sum(stage_scores) / len(stage_scores), 3) if stage_scores else 0.0

    completeness_min = min(stage_means.values()) if stage_means else 0.0
    completeness_mean = round(sum(stage_means.values()) / len(stage_means), 3) if stage_means else 0.0
    # The gate is per-stage, not on the mean: a strong HLD must not mask a weak LLD.
    completeness_pass = completeness_min >= THRESHOLDS["completeness_stage_min"]
    min_stage = min(stage_means, key=stage_means.get) if stage_means else ""

    # Propagation pass
    prop_pass = propagation_result.get("pass", False)

    # Overall verdict
    verdict = "GO" if (traj_pass and completeness_pass and prop_pass) else "NO-GO"

    # Per-scenario combined rows
    scenario_rows = []
    for i, sc in enumerate(scenarios):
        traj = trajectory_results[i] if i < len(trajectory_results) else {}
        comp = completeness_results[i] if i < len(completeness_results) else {}
        scenario_rows.append({
            "id": sc["id"],
            "title": sc["title"],
            "requirement": sc["requirement"],
            "trajectory": traj,
            "completeness": {k: comp.get(k) for k in [*STAGE_NAMES, "mean"]},
            "duration_s": traj.get("duration_s"),
            "error": traj.get("error"),
        })

    return {
        "run_id": run_id,
        "verdict": verdict,
        "scenarios_total": len(scenarios),
        "scenarios_run": len(trajectory_results),
        "trajectory": {
            "pass": traj_pass,
            "score": round(traj_rate, 3),
            "passed": passed_traj,
            "total": len(trajectory_results),
            "threshold": THRESHOLDS["trajectory_rate"],
        },
        "completeness": {
            "pass": completeness_pass,
            "mean": completeness_mean,
            # `min` is the number the gate is applied to — surface it so the UI
            # can show the value that actually drives pass/fail.
            "min": completeness_min,
            "min_stage": min_stage,
            "threshold": THRESHOLDS["completeness_stage_min"],
            **{stage: {"score": stage_means[stage], "threshold": THRESHOLDS["completeness_stage_min"]}
               for stage in STAGE_NAMES},
        },
        "propagation": {**propagation_result, "threshold": True},
        "thresholds": THRESHOLDS,
        "scenarios": scenario_rows,
        "duration_s": round(duration_s, 1),
    }
