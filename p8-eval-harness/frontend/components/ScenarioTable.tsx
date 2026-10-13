"use client";

import { Fragment, useState } from "react";
import { ChevronDown, ChevronRight, AlertCircle, CheckCircle2, XCircle } from "lucide-react";
import type { EvalResults, ScenarioRow } from "@/lib/types";

const STAGES = ["scoping", "solution", "hld", "lld"] as const;

const STAGE_COLORS: Record<string, string> = {
  scoping: "text-stage-scoping",
  solution: "text-stage-solution",
  hld: "text-stage-hld",
  lld: "text-stage-lld",
};

function ScoreCell({ score }: { score: number | null | undefined }) {
  if (score === null || score === undefined) {
    return <span className="font-mono text-[11px] text-muted-foreground">—</span>;
  }
  const pct = Math.round(score * 100);
  const color = score >= 0.70 ? "text-go" : "text-nogo";
  return <span className={`font-mono text-[12px] font-medium ${color}`}>{pct}%</span>;
}

function ScenarioDetail({ row }: { row: ScenarioRow }) {
  return (
    <tr>
      <td colSpan={9} className="px-4 pb-3 pt-0">
        <div className="rounded-lg border border-border-subtle bg-surface-raised p-3 text-[11px] text-muted-foreground space-y-2">
          <p className="text-foreground/80 leading-relaxed">{row.requirement}</p>

          {row.error && (
            <div className="flex items-start gap-1.5 text-nogo">
              <AlertCircle className="w-3.5 h-3.5 shrink-0 mt-0.5" />
              <span>Error: {row.error}</span>
            </div>
          )}

          <div className="flex flex-wrap gap-2 pt-1">
            {STAGES.map((s) => {
              const present = row.trajectory.stages_completed?.includes(s);
              const score = row.completeness?.[s];
              return (
                <div key={s} className="flex items-center gap-1.5 bg-surface px-2 py-1 rounded-md border border-border">
                  {present ? (
                    <CheckCircle2 className="w-3 h-3 text-go" />
                  ) : (
                    <XCircle className="w-3 h-3 text-nogo" />
                  )}
                  <span className={`capitalize font-medium ${STAGE_COLORS[s]}`}>{s}</span>
                  {score !== null && score !== undefined && (
                    <span className={`font-mono ${score >= 0.70 ? "text-go" : "text-nogo"}`}>
                      {Math.round(score * 100)}%
                    </span>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      </td>
    </tr>
  );
}

interface Props {
  results: EvalResults;
}

export function ScenarioTable({ results }: Props) {
  const [expanded, setExpanded] = useState<Set<number>>(new Set());

  const toggle = (id: number) =>
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });

  return (
    <div className="rounded-xl border border-border bg-surface overflow-hidden">
      <div className="px-4 py-3 border-b border-border flex items-center justify-between">
        <h2 className="text-[13px] font-semibold text-foreground">Scenario Results</h2>
        <span className="text-[11px] text-muted-foreground font-mono">
          {results.trajectory.passed}/{results.trajectory.total} trajectory pass
        </span>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-[12px]">
          <thead>
            <tr className="border-b border-border">
              <th className="px-3 py-2 text-left w-6" />
              <th className="px-3 py-2 text-left text-[10px] font-semibold text-muted-foreground uppercase tracking-wider whitespace-nowrap">
                #
              </th>
              <th className="px-3 py-2 text-left text-[10px] font-semibold text-muted-foreground uppercase tracking-wider">
                Scenario
              </th>
              <th className="px-3 py-2 text-center text-[10px] font-semibold text-muted-foreground uppercase tracking-wider whitespace-nowrap">
                Trajectory
              </th>
              {STAGES.map((s) => (
                <th
                  key={s}
                  className={`px-3 py-2 text-center text-[10px] font-semibold uppercase tracking-wider whitespace-nowrap ${STAGE_COLORS[s]}`}
                >
                  {s.toUpperCase()}
                </th>
              ))}
              <th className="px-3 py-2 text-right text-[10px] font-semibold text-muted-foreground uppercase tracking-wider whitespace-nowrap">
                Duration
              </th>
            </tr>
          </thead>
          <tbody>
            {results.scenarios.map((row) => {
              const isOpen = expanded.has(row.id);
              const trajPass = row.trajectory?.pass;
              return (
                <Fragment key={row.id}>
                  <tr
                    className={`border-b border-border-subtle hover:bg-surface-raised cursor-pointer transition-colors ${
                      isOpen ? "bg-surface-raised" : ""
                    }`}
                    onClick={() => toggle(row.id)}
                  >
                    <td className="px-3 py-2.5 w-6">
                      {isOpen ? (
                        <ChevronDown className="w-3.5 h-3.5 text-muted-foreground" />
                      ) : (
                        <ChevronRight className="w-3.5 h-3.5 text-muted-foreground" />
                      )}
                    </td>
                    <td className="px-3 py-2.5 font-mono text-muted-foreground">{row.id}</td>
                    <td className="px-3 py-2.5 font-medium text-foreground max-w-[200px] truncate">
                      {row.title}
                    </td>
                    <td className="px-3 py-2.5 text-center">
                      <span className={`chip ${trajPass ? "chip-pass" : "chip-fail"}`}>
                        {trajPass ? "pass" : "fail"}
                      </span>
                    </td>
                    {STAGES.map((s) => (
                      <td key={s} className="px-3 py-2.5 text-center">
                        <ScoreCell score={row.completeness?.[s]} />
                      </td>
                    ))}
                    <td className="px-3 py-2.5 text-right font-mono text-muted-foreground">
                      {row.duration_s ? `${row.duration_s.toFixed(0)}s` : "—"}
                    </td>
                  </tr>
                  {isOpen && <ScenarioDetail row={row} />}
                </Fragment>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
