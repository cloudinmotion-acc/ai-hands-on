"use client";

import { CheckCircle2, XCircle, Clock } from "lucide-react";
import type { EvalResults } from "@/lib/types";

interface Props {
  results: EvalResults;
}

export function VerdictBanner({ results }: Props) {
  const isGo = results.verdict === "GO";
  const runDate = new Date(results.run_id).toLocaleString();
  const durationMin = (results.duration_s / 60).toFixed(1);

  const blockers: string[] = [];
  if (!results.trajectory.pass) {
    blockers.push(
      `Trajectory: ${results.trajectory.passed}/${results.trajectory.total} scenarios (need ≥ ${Math.ceil(results.trajectory.threshold * results.trajectory.total)})`
    );
  }
  if (!results.completeness.pass) {
    const failedStages = (["scoping", "solution", "hld", "lld"] as const).filter(
      (s) => (results.completeness[s]?.score ?? 0) < results.completeness.threshold
    );
    blockers.push(`Completeness below 70% on: ${failedStages.join(", ")}`);
  }
  if (!results.propagation.pass) {
    blockers.push(`Propagation: HITL edit did not reach ${results.propagation.check_stage}`);
  }

  return (
    <div
      className={`relative rounded-2xl border overflow-hidden ${
        isGo
          ? "border-go/30 bg-go-dim"
          : "border-nogo/30 bg-nogo-dim"
      }`}
    >
      <div className="px-8 py-6 flex items-start gap-6">
        {/* Verdict icon */}
        <div
          className={`mt-0.5 rounded-full p-2 ${
            isGo ? "bg-go/20 verdict-go" : "bg-nogo/20 verdict-nogo"
          }`}
        >
          {isGo ? (
            <CheckCircle2 className="w-7 h-7 text-go" strokeWidth={1.8} />
          ) : (
            <XCircle className="w-7 h-7 text-nogo" strokeWidth={1.8} />
          )}
        </div>

        {/* Main content */}
        <div className="flex-1 min-w-0">
          <div className="flex items-baseline gap-3 flex-wrap">
            <span
              className={`font-mono text-[32px] font-semibold leading-none tracking-tight ${
                isGo ? "text-go" : "text-nogo"
              }`}
            >
              {results.verdict}
            </span>
            <span className="text-[14px] text-foreground font-medium">
              {isGo
                ? "System meets production criteria"
                : "System does not meet production criteria"}
            </span>
          </div>

          {!isGo && blockers.length > 0 && (
            <ul className="mt-3 space-y-1">
              {blockers.map((b) => (
                <li key={b} className="flex items-start gap-2 text-[12px] text-nogo">
                  <span className="mt-0.5 shrink-0">✗</span>
                  <span>{b}</span>
                </li>
              ))}
            </ul>
          )}

          {isGo && (
            <p className="mt-2 text-[12px] text-go/80">
              All three evaluation dimensions passed their thresholds.
            </p>
          )}
        </div>

        {/* Run metadata */}
        <div className="text-right shrink-0 hidden sm:block">
          <div className="flex items-center gap-1.5 justify-end text-[11px] text-muted-foreground mb-1">
            <Clock className="w-3 h-3" />
            {durationMin} min
          </div>
          <p className="text-[11px] text-muted-foreground">{runDate}</p>
          <p className="text-[11px] text-muted-foreground mt-0.5">
            {results.scenarios_run}/{results.scenarios_total} scenarios run
          </p>
        </div>
      </div>
    </div>
  );
}
