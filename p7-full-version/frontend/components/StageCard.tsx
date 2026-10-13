"use client";

import { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { CheckCircle2, Pencil } from "lucide-react";
import type { Stage, StageResult } from "@/lib/types";
import { EditPanel } from "@/components/EditPanel";

const STAGE_LABELS: Record<string, string> = {
  scoping: "Scoping Analysis",
  solution: "Solution Architecture",
  hld: "High-Level Design",
  lld: "Low-Level Design",
};

interface Props {
  stage: Stage;
  stageResult: StageResult;
  /** True while the LLM is still streaming tokens into this card */
  isStreaming: boolean;
  /** True when the stage completed and is awaiting human approve/edit */
  awaitingReview: boolean;
  /** True when the stage is already approved (read-only display) */
  isApproved?: boolean;
  onApprove: () => void;
  onEdit: (content: string) => void;
  /** Whether approve/edit is currently being processed */
  isActing?: boolean;
}

export function StageCard({
  stage,
  stageResult,
  isStreaming,
  awaitingReview,
  isApproved = false,
  onApprove,
  onEdit,
  isActing = false,
}: Props) {
  const [editOpen, setEditOpen] = useState(false);

  const label = STAGE_LABELS[stage] ?? stage;

  return (
    <div
      className={`rounded-2xl border bg-card flex flex-col gap-0 overflow-hidden trace-entry ${
        awaitingReview
          ? "border-amber-300 shadow-sm"
          : isApproved
            ? "border-emerald-200"
            : "border-border"
      }`}
    >
      {/* Header bar */}
      <div
        className={`flex items-center justify-between px-4 py-2.5 border-b ${
          awaitingReview
            ? "bg-amber-50 border-amber-200"
            : isApproved
              ? "bg-emerald-50/60 border-emerald-200"
              : "bg-muted/30 border-border"
        }`}
      >
        <div className="flex items-center gap-2">
          {isApproved && (
            <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600 shrink-0" />
          )}
          {isStreaming && <span className="wait-spinner" />}
          {awaitingReview && !isStreaming && (
            <span className="w-2 h-2 rounded-full bg-amber-500 animate-pulse shrink-0" />
          )}
          <span className="text-[12px] font-semibold text-foreground">
            {label}
          </span>
          {stageResult.edited && (
            <span className="text-[9px] font-medium text-amber-600 bg-amber-50 border border-amber-200 px-1.5 py-0.5 rounded-full">
              edited
            </span>
          )}
        </div>

        {awaitingReview && !isStreaming && !editOpen && (
          <span className="text-[10px] text-amber-700 font-medium">
            Review required
          </span>
        )}
        {isApproved && (
          <span className="text-[10px] text-emerald-700 font-medium">
            Approved
          </span>
        )}
      </div>

      {/* Content */}
      <div className="px-4 py-3 max-h-[420px] overflow-y-auto">
        <div className="md-prose">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{stageResult.content}</ReactMarkdown>
        </div>
      </div>

      {/* Action bar  -  only shown when awaiting review */}
      {awaitingReview && !isStreaming && (
        <div className="px-4 py-3 border-t border-border bg-card flex items-center gap-2">
          <button
            onClick={onApprove}
            disabled={isActing || editOpen}
            className="flex items-center gap-1.5 px-4 py-1.5 rounded-lg bg-primary text-primary-foreground text-[12px] font-medium hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed transition-opacity"
          >
            {isActing && !editOpen ? (
              <>
                <span className="btn-spinner" /> Processing…
              </>
            ) : (
              <>
                <CheckCircle2 className="w-3.5 h-3.5" /> Approve &amp; Continue
              </>
            )}
          </button>

          <button
            onClick={() => setEditOpen((v) => !v)}
            disabled={isActing}
            className={`flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg text-[12px] font-medium border transition-colors disabled:opacity-50 disabled:cursor-not-allowed ${
              editOpen
                ? "bg-primary/10 text-primary border-primary/30"
                : "bg-card text-muted-foreground border-border hover:text-foreground hover:border-primary/30"
            }`}
          >
            <Pencil className="w-3.5 h-3.5" />
            {editOpen ? "Cancel Edit" : "Edit"}
          </button>
        </div>
      )}

      {/* Edit panel slides in below action bar */}
      {editOpen && awaitingReview && (
        <div className="px-4 pb-4">
          <EditPanel
            initialContent={stageResult.content}
            isSubmitting={isActing}
            onSubmit={(content) => {
              setEditOpen(false);
              onEdit(content);
            }}
            onCancel={() => setEditOpen(false)}
          />
        </div>
      )}
    </div>
  );
}
