"use client";

import {
  X,
  Cpu,
  Zap,
  CheckCircle2,
  Clock,
  Save,
  RefreshCw,
  AlertCircle,
  Flag,
} from "lucide-react";
import type { TraceEntry } from "@/lib/types";

interface Props {
  entries: TraceEntry[];
  onClose: () => void;
}

type IconEl = React.ReactElement | null;

function entryMeta(ev: TraceEntry["event"]): {
  icon: IconEl;
  label: string;
  detail?: string;
  color: string;
} {
  switch (ev.type) {
    case "node_start":
      return {
        icon: <Cpu className="w-3.5 h-3.5" />,
        label: `Agent started  -  ${ev.label}`,
        color: "text-blue-500 bg-blue-50 border-blue-200",
      };
    case "token":
      return {
        icon: <Zap className="w-3 h-3" />,
        label: "Token streamed",
        color: "text-muted-foreground bg-muted/40 border-border",
      };
    case "stage_complete":
      return {
        icon: <CheckCircle2 className="w-3.5 h-3.5" />,
        label: `Stage complete  -  ${ev.stage}`,
        detail: `${ev.content.length} chars · next: ${ev.next_nodes.join(", ") || "interrupt"}`,
        color: "text-emerald-600 bg-emerald-50 border-emerald-200",
      };
    case "checkpoint_saved":
      return {
        icon: <Save className="w-3.5 h-3.5" />,
        label: `Memory saved  -  ${ev.label}`,
        detail: "SQLite checkpoint written, graph paused",
        color: "text-violet-600 bg-violet-50 border-violet-200",
      };
    case "checkpoint_restored":
      return {
        icon: <RefreshCw className="w-3.5 h-3.5" />,
        label: `Memory restored  -  ${ev.label}`,
        detail: "Checkpoint loaded from SQLite, resuming graph",
        color: "text-violet-600 bg-violet-50 border-violet-200",
      };
    case "awaiting_review":
      return {
        icon: <Clock className="w-3.5 h-3.5" />,
        label: `Awaiting review  -  ${ev.stage}`,
        detail: "Paused for human approval / edit",
        color: "text-amber-600 bg-amber-50 border-amber-200",
      };
    case "session_complete":
      return {
        icon: <Flag className="w-3.5 h-3.5" />,
        label: "Session complete",
        detail: "All stages approved, .docx generated",
        color: "text-emerald-700 bg-emerald-50 border-emerald-200",
      };
    case "error":
      return {
        icon: <AlertCircle className="w-3.5 h-3.5" />,
        label: `Error`,
        detail: ev.message,
        color: "text-red-600 bg-red-50 border-red-200",
      };
    case "done":
      return {
        icon: null,
        label: "Stream closed",
        color: "text-muted-foreground bg-muted/30 border-border",
      };
    default:
      return {
        icon: null,
        label: (ev as { type: string }).type,
        color: "text-muted-foreground bg-muted/30 border-border",
      };
  }
}

function fmt(ts: number): string {
  return new Date(ts).toLocaleTimeString("en-GB", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

// Collapse consecutive "token" entries into a single summary row
function collapse(
  entries: TraceEntry[],
): Array<TraceEntry | { type: "token_batch"; count: number; ts: number }> {
  const out: Array<
    TraceEntry | { type: "token_batch"; count: number; ts: number }
  > = [];
  let i = 0;
  while (i < entries.length) {
    const e = entries[i];
    if (e.event.type === "token") {
      let count = 0;
      const ts = e.ts;
      while (i < entries.length && entries[i].event.type === "token") {
        count++;
        i++;
      }
      out.push({ type: "token_batch", count, ts });
    } else {
      out.push(e);
      i++;
    }
  }
  return out;
}

export function TraceDrawer({ entries, onClose }: Props) {
  const rows = collapse(entries);

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/20 backdrop-blur-[2px] z-40"
        onClick={onClose}
      />

      {/* Panel */}
      <div className="fixed top-0 right-0 h-full w-[420px] max-w-[90vw] bg-card border-l border-border shadow-2xl z-50 flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-3.5 border-b border-border bg-card/90 backdrop-blur-sm shrink-0">
          <div>
            <p className="text-[13px] font-semibold text-foreground">
              Full trace
            </p>
            <p className="text-[10px] text-muted-foreground mt-0.5">
              {rows.length} events - all SSE messages from backend
            </p>
          </div>
          <button
            onClick={onClose}
            className="w-7 h-7 rounded-lg flex items-center justify-center text-muted-foreground hover:text-foreground hover:bg-muted/60 transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Legend */}
        <div className="px-5 py-2 border-b border-border bg-muted/30 shrink-0">
          <div className="flex flex-wrap gap-3 text-[9px] font-medium text-muted-foreground">
            <span className="flex items-center gap-1">
              <Cpu className="w-2.5 h-2.5 text-blue-500" /> agent start
            </span>
            <span className="flex items-center gap-1">
              <Save className="w-2.5 h-2.5 text-violet-500" /> memory saved
            </span>
            <span className="flex items-center gap-1">
              <RefreshCw className="w-2.5 h-2.5 text-violet-500" /> memory
              restored
            </span>
            <span className="flex items-center gap-1">
              <Clock className="w-2.5 h-2.5 text-amber-500" /> awaiting review
            </span>
            <span className="flex items-center gap-1">
              <CheckCircle2 className="w-2.5 h-2.5 text-emerald-500" /> complete
            </span>
          </div>
        </div>

        {/* Timeline */}
        <div className="flex-1 overflow-y-auto px-5 py-4">
          {rows.length === 0 ? (
            <div className="flex items-center justify-center h-32 text-[12px] text-muted-foreground">
              No events yet - start a session to see the trace.
            </div>
          ) : (
            <div className="relative">
              {/* Vertical line */}
              <div className="absolute left-[13px] top-0 bottom-0 w-px bg-border" />

              <div className="flex flex-col gap-2">
                {rows.map((row, idx) => {
                  if ("type" in row && row.type === "token_batch") {
                    return (
                      <div key={idx} className="flex items-center gap-3 pl-1">
                        <div className="w-6 h-6 rounded-full bg-muted border border-border flex items-center justify-center shrink-0 z-10">
                          <Zap className="w-2.5 h-2.5 text-muted-foreground" />
                        </div>
                        <div className="flex items-center gap-2 min-w-0">
                          <span className="text-[10px] text-muted-foreground">
                            {row.count} tokens streamed
                          </span>
                          <span className="text-[9px] text-muted-foreground/50 font-mono shrink-0">
                            {fmt(row.ts)}
                          </span>
                        </div>
                      </div>
                    );
                  }

                  const entry = row as TraceEntry;
                  const { icon, label, detail, color } = entryMeta(entry.event);
                  const [textColor] = color.split(" ");

                  return (
                    <div key={idx} className="flex items-start gap-3 pl-1">
                      {/* Icon dot */}
                      <div
                        className={`w-6 h-6 rounded-full border flex items-center justify-center shrink-0 z-10 ${color}`}
                      >
                        {icon ?? (
                          <span className="w-1.5 h-1.5 rounded-full bg-current" />
                        )}
                      </div>

                      {/* Content */}
                      <div className="flex-1 min-w-0 pb-1">
                        <div className="flex items-baseline justify-between gap-2">
                          <span
                            className={`text-[11px] font-medium ${textColor}`}
                          >
                            {label}
                          </span>
                          <span className="text-[9px] text-muted-foreground font-mono shrink-0">
                            {fmt(entry.ts)}
                          </span>
                        </div>
                        {detail && (
                          <p className="text-[10px] text-muted-foreground mt-0.5 leading-relaxed">
                            {detail}
                          </p>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      </div>
    </>
  );
}
