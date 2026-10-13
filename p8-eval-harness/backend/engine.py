"""
Eval engine: orchestrates the full P8 evaluation pipeline.

Called by both main.py (SSE endpoint) and run_eval.py (CLI).
Uses asyncio.gather() with a semaphore to run scenarios concurrently.
"""

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Awaitable

from runner import run_scenario, create_session
from evaluators import trajectory as traj_eval
from evaluators import completeness as comp_eval
from evaluators import propagation as prop_eval
from scorecard import build_scorecard

logger = logging.getLogger("p8.engine")


@dataclass
class EvalConfig:
    p7_url: str = "http://localhost:8000"
    scenarios_file: str = "scenarios/requirements.json"
    checklists_dir: str = "checklists"
    results_dir: str = "../results"
    judge_model: str = "nvidia/nemotron-3-super-120b-a12b"
    nvidia_api_key: str = ""
    nvidia_base_url: str = "https://integrate.api.nvidia.com/v1"
    concurrency: int = 3
    judge_concurrency: int = 3   # max in-flight LLM judge calls across all scenarios
    quick: bool = False
    skip_propagation: bool = False
    scenario_ids: list[int] = field(default_factory=list)


def _load_scenarios(config: EvalConfig) -> list[dict]:
    with open(config.scenarios_file) as f:
        all_scenarios = json.load(f)
    if config.scenario_ids:
        all_scenarios = [s for s in all_scenarios if s["id"] in config.scenario_ids]
    if config.quick:
        all_scenarios = all_scenarios[:3]
    return all_scenarios


def _load_checklists(config: EvalConfig) -> dict[str, list[str]]:
    checklists = {}
    for stage in ["scoping", "solution", "hld", "lld"]:
        p = Path(config.checklists_dir) / f"{stage}.json"
        with open(p) as f:
            data = json.load(f)
        checklists[stage] = data["items"]
    return checklists


async def run_eval(
    config: EvalConfig,
    on_event: Callable[[dict], Awaitable[None]],
) -> dict:
    """
    Run the full eval pipeline.

    on_event() is called for each progress event (used by SSE stream and CLI printer).

    Events emitted:
        {"type": "eval_start", "scenarios_count": N, "quick": bool}
        {"type": "scenario_start", "id": N, "title": "...", "index": N, "total": N}
        {"type": "scenario_done", "id": N, "title": "...", "trajectory": {...}, "error": None}
        {"type": "completeness_start", "scenarios_count": N}
        {"type": "completeness_done", "mean": 0.76}
        {"type": "propagation_start"}
        {"type": "propagation_done", "pass": True}
        {"type": "scorecard_ready", "verdict": "GO", "result": {...}}
        {"type": "done"}
    """
    t0 = time.monotonic()
    run_id = datetime.now(timezone.utc).isoformat(timespec="seconds")

    scenarios = _load_scenarios(config)
    checklists = _load_checklists(config)

    await on_event({"type": "eval_start", "scenarios_count": len(scenarios), "quick": config.quick})

    # Phase 1: run scenarios through P7 and collect trajectory results
    semaphore = asyncio.Semaphore(config.concurrency)
    scenario_results: list[tuple[int, dict, dict]] = []

    async def _run_one(i: int, sc: dict):
        async with semaphore:
            await on_event({
                "type": "scenario_start",
                "id": sc["id"],
                "title": sc["title"],
                "index": i + 1,
                "total": len(scenarios),
            })
            try:
                sid = await create_session(p7_url=config.p7_url)
                run_result = await run_scenario(
                    requirement=sc["requirement"],
                    p7_url=config.p7_url,
                    session_id=sid,
                )
                traj = traj_eval.evaluate(
                    run_result["stages_completed"],
                    run_result["stage_order"],
                )
                traj["duration_s"] = run_result["duration_s"]
                traj["error"] = run_result["error"]

                await on_event({
                    "type": "scenario_done",
                    "id": sc["id"],
                    "title": sc["title"],
                    "trajectory": traj,
                    "error": run_result["error"],
                })
                return (i, run_result, traj)
            except Exception as exc:
                logger.error(f"Scenario {sc['id']} failed: {exc}", exc_info=True)
                empty_run = {"stages_completed": [], "stage_order": [], "outputs": {},
                             "duration_s": 0.0, "error": str(exc)}
                empty_traj = traj_eval.evaluate([], [])
                empty_traj["duration_s"] = 0.0
                empty_traj["error"] = str(exc)
                await on_event({
                    "type": "scenario_done",
                    "id": sc["id"],
                    "title": sc["title"],
                    "trajectory": empty_traj,
                    "error": str(exc),
                })
                return (i, empty_run, empty_traj)

    tasks = [_run_one(i, sc) for i, sc in enumerate(scenarios)]
    ordered_results = await asyncio.gather(*tasks)
    ordered_results = sorted(ordered_results, key=lambda x: x[0])
    run_results = [r for _, r, _ in ordered_results]
    trajectory_results = [t for _, _, t in ordered_results]

    # Phase 2: completeness eval (LLM judge) and propagation (can overlap)
    await on_event({"type": "completeness_start", "scenarios_count": len(scenarios)})

    async def _run_completeness():
        # One semaphore shared across every scenario so the total in-flight judge
        # calls stay capped — a 12-call burst does draw a real 429 from NVIDIA.
        judge_sem = asyncio.Semaphore(config.judge_concurrency)
        results = await asyncio.gather(*[
            comp_eval.evaluate(
                outputs=run_result["outputs"],
                checklists=checklists,
                api_key=config.nvidia_api_key,
                base_url=config.nvidia_base_url,
                judge_model=config.judge_model,
                sem=judge_sem,
            )
            for run_result in run_results
        ])
        results = list(results)
        mean = round(sum(r["mean"] for r in results) / len(results), 3) if results else 0.0
        await on_event({"type": "completeness_done", "mean": mean})
        return results

    async def _run_propagation():
        if config.skip_propagation:
            return {"pass": None, "error": "skipped", "evidence": "", "found": False,
                    "scenario": "", "edit_stage": "scoping", "check_stage": "hld",
                    "injected": "", "search_term": "offline"}
        await on_event({"type": "propagation_start"})
        result = await prop_eval.evaluate(p7_url=config.p7_url)
        await on_event({"type": "propagation_done", "pass": result["pass"]})
        return result

    completeness_results, propagation_result = await asyncio.gather(
        _run_completeness(), _run_propagation()
    )

    # Phase 3: build scorecard
    results = build_scorecard(
        scenarios=scenarios,
        trajectory_results=trajectory_results,
        completeness_results=completeness_results,
        propagation_result=propagation_result,
        run_id=run_id,
        duration_s=time.monotonic() - t0,
    )

    # Write results to disk
    results_dir = Path(config.results_dir)
    results_dir.mkdir(parents=True, exist_ok=True)
    ts = run_id.replace(":", "-").replace("+", "")
    (results_dir / f"report_{ts}.json").write_text(
        json.dumps(results, indent=2), encoding="utf-8"
    )
    (results_dir / "latest.json").write_text(
        json.dumps(results, indent=2), encoding="utf-8"
    )

    await on_event({"type": "scorecard_ready", "verdict": results["verdict"], "result": results})
    await on_event({"type": "done"})

    return results
