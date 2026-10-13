"""
P8 CLI entry point.

Usage:
  python run_eval.py                     # full run, all 15 scenarios
  python run_eval.py --quick             # 3 scenarios (CI / quick smoke test)
  python run_eval.py --skip-propagation  # skip the HITL propagation test
  python run_eval.py --p7-url http://host:8000
  python run_eval.py --concurrency 2
  python run_eval.py --scenarios 1,2,5   # run specific scenario IDs only
"""

import argparse
import asyncio
import os
import sys

from dotenv import load_dotenv
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.table import Table
from rich import box

from engine import EvalConfig, run_eval

load_dotenv()
console = Console()


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="P8 Eval Harness CLI")
    p.add_argument("--p7-url", default=os.environ.get("P7_URL", "http://localhost:8000"))
    p.add_argument("--quick", action="store_true", help="Run only 3 scenarios")
    p.add_argument("--skip-propagation", action="store_true")
    p.add_argument("--concurrency", type=int, default=int(os.environ.get("CONCURRENCY", "3")))
    p.add_argument("--scenarios", type=str, default="", help="Comma-separated scenario IDs")
    p.add_argument("--results-dir", default=os.environ.get("RESULTS_DIR", "../results"))
    return p.parse_args()


def _scenario_ids(args) -> list[int]:
    if args.scenarios:
        return [int(x.strip()) for x in args.scenarios.split(",") if x.strip()]
    return []


async def main():
    args = _parse_args()

    config = EvalConfig(
        p7_url=args.p7_url,
        scenarios_file="scenarios/requirements.json",
        checklists_dir="checklists",
        results_dir=args.results_dir,
        judge_model=os.environ.get("JUDGE_MODEL", "nvidia/nemotron-3-super-120b-a12b"),
        nvidia_api_key=os.environ.get("NVIDIA_API_KEY", ""),
        nvidia_base_url=os.environ.get("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1"),
        concurrency=args.concurrency,
        quick=args.quick,
        skip_propagation=args.skip_propagation,
        scenario_ids=_scenario_ids(args),
    )

    if not config.nvidia_api_key:
        console.print("[bold red]Error:[/] NVIDIA_API_KEY not set. Add it to .env or export it.")
        sys.exit(1)

    console.print(Panel(
        f"[bold]P8 Eval Harness[/]\n"
        f"P7 URL: {config.p7_url}  |  "
        f"Scenarios: {'3 (quick)' if config.quick else 'all 15'}  |  "
        f"Concurrency: {config.concurrency}",
        border_style="blue",
    ))

    completed_scenarios: list[dict] = []

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Running evaluation...", total=None)

        async def on_event(event: dict):
            ev_type = event.get("type")

            if ev_type == "eval_start":
                progress.update(task, description=f"Running {event['scenarios_count']} scenarios...")

            elif ev_type == "scenario_start":
                progress.update(
                    task,
                    description=(
                        f"[{event['index']}/{event['total']}] "
                        f"Scenario {event['id']}: {event['title'][:40]}..."
                    ),
                )

            elif ev_type == "scenario_done":
                traj = event.get("trajectory", {})
                status = "[green]PASS[/]" if traj.get("pass") else "[red]FAIL[/]"
                missing = traj.get("missing", [])
                detail = f" (missing: {', '.join(missing)})" if missing else ""
                console.print(
                    f"  Scenario {event['id']:2d} {event['title'][:35]:<35} "
                    f"Trajectory: {status}{detail}"
                )
                completed_scenarios.append(event)

            elif ev_type == "completeness_start":
                progress.update(task, description="Running LLM completeness judge...")

            elif ev_type == "completeness_done":
                console.print(f"  Completeness mean score: [cyan]{event['mean']:.0%}[/]")

            elif ev_type == "propagation_start":
                progress.update(task, description="Running propagation test (HITL edit)...")

            elif ev_type == "propagation_done":
                status = "[green]PASS[/]" if event.get("pass") else "[red]FAIL[/]"
                console.print(f"  Propagation test: {status}")

            elif ev_type == "scorecard_ready":
                progress.update(task, description="Writing results...")

            elif ev_type == "done":
                progress.update(task, description="Complete")

        results = await run_eval(config, on_event)

    # Print final scorecard table
    _print_scorecard(results)

    verdict = results.get("verdict", "NO-GO")
    if verdict == "GO":
        console.print(f"\n[bold green on black] ✓ VERDICT: GO — System is production-ready [/]")
        sys.exit(0)
    else:
        console.print(f"\n[bold red on black] ✗ VERDICT: NO-GO — Thresholds not met [/]")
        sys.exit(1)


def _print_scorecard(results: dict):
    console.print()

    t = Table(title="Scorecard", box=box.ROUNDED, border_style="dim")
    t.add_column("Dimension", style="bold")
    t.add_column("Score")
    t.add_column("Threshold")
    t.add_column("Result")

    traj = results.get("trajectory", {})
    t.add_row(
        "Trajectory",
        f"{traj.get('passed', 0)}/{traj.get('total', 0)} scenarios",
        f"≥ {traj.get('threshold', 0):.0%}",
        "[green]PASS[/]" if traj.get("pass") else "[red]FAIL[/]",
    )

    comp = results.get("completeness", {})
    for stage in ["scoping", "solution", "hld", "lld"]:
        stage_data = comp.get(stage, {})
        score = stage_data.get("score", 0) if isinstance(stage_data, dict) else 0
        threshold = stage_data.get("threshold", 0.70) if isinstance(stage_data, dict) else 0.70
        t.add_row(
            f"  Completeness – {stage.capitalize()}",
            f"{score:.0%}",
            f"≥ {threshold:.0%}",
            "[green]PASS[/]" if score >= threshold else "[red]FAIL[/]",
        )

    prop = results.get("propagation", {})
    t.add_row(
        "Propagation (HITL edit)",
        "Found" if prop.get("found") else "Not found",
        "Must propagate",
        "[green]PASS[/]" if prop.get("pass") else "[red]FAIL[/]",
    )

    console.print(t)


if __name__ == "__main__":
    asyncio.run(main())
