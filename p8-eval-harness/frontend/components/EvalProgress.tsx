"use client";

import { CheckCircle2, XCircle, Loader2, Info } from "lucide-react";
import type { ProgressItem } from "@/lib/types";

interface Props {
  items: ProgressItem[];
  isRunning: boolean;
  phase: string;
}

const statusIcon = (status: ProgressItem["status"]) => {
  if (status === "running")
    return <Loader2 className="w-3.5 h-3.5 text-primary animate-spin shrink-0" />;
  if (status === "pass")
    return <CheckCircle2 className="w-3.5 h-3.5 text-go shrink-0" />;
  if (status === "fail")
    return <XCircle className="w-3.5 h-3.5 text-nogo shrink-0" />;
  return <Info className="w-3.5 h-3.5 text-muted-foreground shrink-0" />;
};

export function EvalProgress({ items, isRunning, phase }: Props) {
  return (
    <div className="rounded-xl border border-primary/20 bg-surface overflow-hidden">
      <div className="flex items-center gap-2 px-4 py-3 border-b border-primary/15 bg-primary-dim">
        {isRunning && <Loader2 className="w-4 h-4 text-primary animate-spin" />}
        <span className="text-[13px] font-semibold text-primary">
          {isRunning ? phase || "Running evaluation…" : "Evaluation complete"}
        </span>
      </div>

      <div className="px-4 py-3 max-h-[360px] overflow-y-auto space-y-1.5">
        {items.length === 0 && (
          <p className="text-[12px] text-muted-foreground">Starting evaluation pipeline…</p>
        )}
        {items.map((item) => (
          <div
            key={item.id}
            className="flex items-start gap-2.5 py-0.5 slide-in"
          >
            {statusIcon(item.status)}
            <span
              className={`text-[12px] leading-snug ${
                item.status === "running"
                  ? "text-foreground"
                  : item.status === "pass"
                    ? "text-go/90"
                    : item.status === "fail"
                      ? "text-nogo/90"
                      : "text-muted-foreground"
              }`}
            >
              {item.text}
            </span>
            <span className="ml-auto text-[10px] font-mono text-muted-foreground shrink-0 mt-0.5">
              {new Date(item.ts).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" })}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
