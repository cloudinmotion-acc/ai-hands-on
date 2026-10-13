"use client";

import { ReactNode } from "react";

interface Props {
  label: string;
  value: string;
  sub?: string;
  pass: boolean | null;
  bar?: number;
  threshold?: number;
  icon?: ReactNode;
}

export function MetricCard({ label, value, sub, pass, bar, threshold, icon }: Props) {
  const statusColor =
    pass === null
      ? "text-muted-foreground"
      : pass
        ? "text-go"
        : "text-nogo";

  const barColor =
    pass === null
      ? "bg-muted-foreground/40"
      : pass
        ? "bg-go"
        : "bg-nogo";

  return (
    <div className="rounded-xl border border-border bg-surface px-4 py-3.5 flex flex-col gap-2">
      <div className="flex items-center gap-2 text-[11px] text-muted-foreground font-medium uppercase tracking-wider">
        {icon && <span className="opacity-70">{icon}</span>}
        {label}
      </div>

      <div className="flex items-end gap-2">
        <span className={`font-mono text-[24px] font-semibold leading-none ${statusColor}`}>
          {value}
        </span>
        {sub && (
          <span className="text-[11px] text-muted-foreground mb-0.5">{sub}</span>
        )}
      </div>

      {bar !== undefined && (
        <div>
          <div className="score-bar">
            <div
              className={`score-bar-fill ${barColor}`}
              style={{ width: `${Math.min(100, Math.round(bar * 100))}%` }}
            />
          </div>
          {threshold !== undefined && (
            <div className="flex justify-between mt-1">
              <span className="text-[9px] text-muted-foreground font-mono">0%</span>
              <span className="text-[9px] text-muted-foreground font-mono">
                threshold {Math.round(threshold * 100)}%
              </span>
              <span className="text-[9px] text-muted-foreground font-mono">100%</span>
            </div>
          )}
        </div>
      )}

      {pass !== null && (
        <span className={`chip ${pass ? "chip-pass" : "chip-fail"} self-start`}>
          {pass ? "pass" : "fail"}
        </span>
      )}
    </div>
  );
}
