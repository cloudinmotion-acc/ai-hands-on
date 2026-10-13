"use client";

import { CheckCircle2, Circle, RefreshCw } from "lucide-react";
import type { Stage, SessionState } from "@/lib/types";

interface StageInfo {
  key: Stage;
  label: string;
  sub: string;
}

const STAGES: StageInfo[] = [
  { key: "scoping", label: "Scoping", sub: "scope · assumptions · risks" },
  { key: "solution", label: "Solution", sub: "approach · stack · NFRs" },
  { key: "hld", label: "HLD", sub: "components · data flow" },
  { key: "lld", label: "LLD", sub: "schemas · API contracts" },
  { key: "doc", label: "Document", sub: "assembles approved content" },
];

// Map a stage key to the corresponding state field
function getStageResult(state: SessionState | null, key: Stage) {
  if (!state) return null;
  if (key === "scoping") return state.scope;
  if (key === "solution") return state.solution;
  if (key === "hld") return state.hld;
  if (key === "lld") return state.lld;
  return null;
}

interface Props {
  state: SessionState | null;
  streamingStage: Stage | null;
  awaitingReview: boolean;
  onRegenerate?: (stage: Stage) => void;
}

export function StageProgress({
  state,
  streamingStage,
  awaitingReview,
  onRegenerate,
}: Props) {
  const currentStage = state?.current_stage ?? null;
  const isComplete = currentStage === "complete";

  return (
    <nav className="flex flex-col gap-1 py-1">
      {STAGES.map((s, idx) => {
        const result = getStageResult(state, s.key);
        const isApproved = result?.approved === true;
        const isStreaming = streamingStage === s.key && !awaitingReview;
        const isAwaitingReview = s.key === currentStage && awaitingReview;
        const isDocStage = s.key === "doc";
        const isDocRunning = isDocStage && streamingStage === "doc";
        const isDocDone = isDocStage && isComplete;
        const canRegenerate = isApproved && !isDocStage && onRegenerate;

        let iconEl: React.ReactNode;
        let textColor = "text-muted-foreground";
        let dotColor = "";

        if (isApproved || isDocDone) {
          iconEl = (
            <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
          );
          textColor = "text-foreground";
        } else if (isStreaming || isDocRunning) {
          iconEl = <span className="wait-spinner shrink-0" />;
          textColor = "text-primary";
        } else if (isAwaitingReview) {
          iconEl = (
            <span className="w-4 h-4 shrink-0 flex items-center justify-center">
              <span className="w-2.5 h-2.5 rounded-full bg-amber-500 animate-pulse" />
            </span>
          );
          textColor = "text-amber-700";
        } else {
          iconEl = <Circle className="w-4 h-4 text-border shrink-0" />;
        }

        return (
          <div key={s.key} className="group relative">
            {/* Connecting line */}
            {idx < STAGES.length - 1 && (
              <div className="absolute left-[7px] top-8 w-px h-4 bg-border" />
            )}

            <div
              className={`flex items-start gap-2.5 px-2 py-2 rounded-lg transition-colors ${
                canRegenerate ? "cursor-pointer hover:bg-muted/70" : ""
              }`}
              onClick={() => {
                if (canRegenerate) onRegenerate(s.key);
              }}
            >
              <div className="mt-0.5">{iconEl}</div>

              <div className="flex-1 min-w-0">
                <div
                  className={`text-[12px] font-semibold leading-tight ${textColor}`}
                >
                  {s.label}
                  {result?.edited && (
                    <span className="ml-1.5 text-[9px] font-medium text-amber-600 bg-amber-50 border border-amber-200 px-1 py-0.5 rounded-full align-middle">
                      edited
                    </span>
                  )}
                </div>
                <div className="text-[10px] text-muted-foreground leading-tight mt-0.5">
                  {s.sub}
                </div>
              </div>

              {/* Regenerate icon  -  shows on hover for approved stages */}
              {canRegenerate && (
                <RefreshCw className="w-3 h-3 text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity mt-1 shrink-0" />
              )}
            </div>
          </div>
        );
      })}
    </nav>
  );
}
