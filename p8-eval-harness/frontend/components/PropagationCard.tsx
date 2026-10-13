"use client";

import { GitBranch, CheckCircle2, XCircle, ArrowRight } from "lucide-react";
import type { PropagationResult } from "@/lib/types";

interface Props {
  propagation: PropagationResult & { threshold: boolean };
}

export function PropagationCard({ propagation }: Props) {
  const isPass = propagation.pass;
  const isSkipped = propagation.error === "skipped";

  return (
    <div
      className={`rounded-xl border overflow-hidden ${
        isSkipped
          ? "border-border"
          : isPass
            ? "border-go/25"
            : "border-nogo/25"
      }`}
    >
      <div
        className={`flex items-center gap-3 px-4 py-3 border-b ${
          isSkipped
            ? "bg-surface border-border"
            : isPass
              ? "bg-go-dim border-go/20"
              : "bg-nogo-dim border-nogo/20"
        }`}
      >
        <GitBranch
          className={`w-4 h-4 ${isSkipped ? "text-muted-foreground" : isPass ? "text-go" : "text-nogo"}`}
        />
        <span className="text-[13px] font-semibold text-foreground">
          Propagation Test — HITL Edit
        </span>
        {!isSkipped && (
          <span className={`chip ml-auto ${isPass ? "chip-pass" : "chip-fail"}`}>
            {isPass ? "pass" : "fail"}
          </span>
        )}
        {isSkipped && <span className="chip chip-skip ml-auto">skipped</span>}
      </div>

      <div className="px-4 py-4 bg-surface space-y-3">
        {isSkipped ? (
          <p className="text-[12px] text-muted-foreground">
            Propagation test was skipped. Run without <code className="font-mono text-[11px]">--skip-propagation</code> to enable it.
          </p>
        ) : (
          <>
            {/* Flow: edit_stage → check_stage */}
            <div className="flex items-center gap-2 text-[11px] text-muted-foreground font-mono">
              <span className="capitalize text-primary">{propagation.edit_stage}</span>
              <ArrowRight className="w-3 h-3" />
              <span className="capitalize text-primary">{propagation.check_stage}</span>
            </div>

            {/* Injected constraint */}
            <div>
              <p className="text-[10px] text-muted-foreground uppercase tracking-wider mb-1">
                Injected constraint
              </p>
              <div className="bg-surface-raised border border-border rounded-lg px-3 py-2 text-[11px] text-foreground/80 font-mono leading-relaxed">
                {propagation.injected}
              </div>
            </div>

            {/* Search term + result */}
            <div className="flex items-start gap-3">
              <div className="flex-1">
                <p className="text-[10px] text-muted-foreground uppercase tracking-wider mb-1">
                  Search in {propagation.check_stage}
                </p>
                <code className="font-mono text-[12px] text-primary bg-primary-dim px-2 py-0.5 rounded">
                  &quot;{propagation.search_term}&quot;
                </code>
              </div>
              <div className="flex items-center gap-1.5 mt-4">
                {propagation.found ? (
                  <CheckCircle2 className="w-4 h-4 text-go" />
                ) : (
                  <XCircle className="w-4 h-4 text-nogo" />
                )}
                <span className={`text-[12px] font-medium ${propagation.found ? "text-go" : "text-nogo"}`}>
                  {propagation.found ? "Found — edit propagated" : "Not found — edit lost"}
                </span>
              </div>
            </div>

            {/* Evidence */}
            {propagation.evidence && (
              <div>
                <p className="text-[10px] text-muted-foreground uppercase tracking-wider mb-1">
                  Evidence (from HLD)
                </p>
                <blockquote className="border-l-2 border-go/40 pl-3 text-[11px] text-foreground/70 italic leading-relaxed break-words">
                  &ldquo;
                  {/* Strip markdown table pipes, bold markers, and leading/trailing pipes */}
                  {propagation.evidence
                    .replace(/\*\*/g, "")
                    .replace(/^\|?\s*/, "")
                    .replace(/\s*\|?\s*$/, "")
                    .replace(/\s*\|\s*/g, " · ")
                    .trim()
                    .slice(0, 240)}
                  {propagation.evidence.length > 240 ? "…" : ""}
                  &rdquo;
                </blockquote>
              </div>
            )}

            {propagation.error && !isSkipped && (
              <div className="flex items-center gap-1.5 text-nogo text-[11px]">
                <XCircle className="w-3.5 h-3.5" />
                <span>{propagation.error}</span>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
