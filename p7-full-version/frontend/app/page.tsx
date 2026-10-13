"use client";

import { useState, useEffect, useRef } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  BrainCircuit,
  Sparkles,
  RotateCcw,
  ArrowRight,
  Cpu,
  Save,
  RefreshCw,
  Clock,
  CheckCircle2,
  AlertCircle,
  GitBranch,
} from "lucide-react";

import type {
  Stage,
  SessionState,
  SSEEvent,
  StageResult,
  TraceEntry,
} from "@/lib/types";
import { saveSession, loadSession, clearSession } from "@/lib/session";
import {
  createSession,
  getState,
  startSession,
  resumeSession,
  regenerateFrom,
} from "@/lib/api";
import { StageProgress } from "@/components/StageProgress";
import { StageCard } from "@/components/StageCard";
import { DocumentPreview } from "@/components/DocumentPreview";
import { TraceDrawer } from "@/components/TraceDrawer";

// Helper: return the StageResult for a given stage key from session state
function getResult(
  state: SessionState | null,
  stage: Stage,
): StageResult | null {
  if (!state) return null;
  if (stage === "scoping") return state.scope;
  if (stage === "solution") return state.solution;
  if (stage === "hld") return state.hld;
  if (stage === "lld") return state.lld;
  return null;
}

// Ordered list of reviewable stages
const REVIEWABLE_STAGES: Stage[] = ["scoping", "solution", "hld", "lld"];

// Downstream stage labels for regeneration confirmation
const STAGE_LABELS: Record<string, string> = {
  scoping: "Scoping",
  solution: "Solution",
  hld: "HLD",
  lld: "LLD",
  doc: "Document",
};

function getDownstreamStages(from: Stage): Stage[] {
  const all: Stage[] = ["scoping", "solution", "hld", "lld", "doc"];
  const idx = all.indexOf(from);
  return idx >= 0 ? all.slice(idx) : [];
}

// ── Activity feed helpers ─────────────────────────────────────────────────────

interface ActivityItem {
  ts: number;
  icon: React.ReactNode;
  label: string;
  color: string;
}

function toActivityItem(ev: SSEEvent, ts: number): ActivityItem | null {
  switch (ev.type) {
    case "node_start":
      return {
        ts,
        label: `Agent: ${ev.label}`,
        icon: <Cpu className="w-3 h-3" />,
        color: "text-blue-500",
      };
    case "checkpoint_saved":
      return {
        ts,
        label: `Memory saved → ${ev.stage}`,
        icon: <Save className="w-3 h-3" />,
        color: "text-violet-500",
      };
    case "checkpoint_restored":
      return {
        ts,
        label: `Memory restored ← ${ev.stage}`,
        icon: <RefreshCw className="w-3 h-3" />,
        color: "text-violet-500",
      };
    case "awaiting_review":
      return {
        ts,
        label: `Review: ${ev.stage}`,
        icon: <Clock className="w-3 h-3" />,
        color: "text-amber-500",
      };
    case "stage_complete":
      return {
        ts,
        label: `Done: ${ev.stage}`,
        icon: <CheckCircle2 className="w-3 h-3" />,
        color: "text-emerald-500",
      };
    case "error":
      return {
        ts,
        label: `Error`,
        icon: <AlertCircle className="w-3 h-3" />,
        color: "text-red-500",
      };
    default:
      return null;
  }
}

function fmtTime(ts: number): string {
  return new Date(ts).toLocaleTimeString("en-GB", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

// ─────────────────────────────────────────────────────────────────────────────

export default function Home() {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [sessionState, setSessionState] = useState<SessionState | null>(null);
  const [streamingStage, setStreamingStage] = useState<Stage | null>(null);
  const [streamingContent, setStreamingContent] = useState<string>("");
  const [awaitingReview, setAwaitingReview] = useState<boolean>(false);
  const [isComplete, setIsComplete] = useState<boolean>(false);
  const [requirement, setRequirement] = useState<string>("");
  const [isStarting, setIsStarting] = useState<boolean>(false);
  const [isActing, setIsActing] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // Trace
  const [traceEntries, setTraceEntries] = useState<TraceEntry[]>([]);
  const [showTrace, setShowTrace] = useState<boolean>(false);

  // Activity feed (sidebar)  -  only show meaningful events, last 8
  const [activityFeed, setActivityFeed] = useState<ActivityItem[]>([]);

  const abortRef = useRef<AbortController | null>(null);
  const sessionIdRef = useRef<string | null>(null);

  // ── On mount: restore session from localStorage ───────────────────────────
  useEffect(() => {
    const saved = loadSession();
    if (!saved) return;

    getState(saved)
      .then((raw) => {
        const s = raw as SessionState;
        setSessionId(saved);
        sessionIdRef.current = saved;
        setSessionState(s);
        setRequirement(s.requirement ?? "");
        if (s.current_stage === "complete") {
          setIsComplete(true);
        } else if (s.awaiting_review) {
          setAwaitingReview(true);
        }
        // Add a synthetic activity item for the restore
        setActivityFeed([
          {
            ts: Date.now(),
            label: `Session restored`,
            icon: <RefreshCw className="w-3 h-3" />,
            color: "text-violet-500",
          },
        ]);
      })
      .catch(() => {
        clearSession();
      });
  }, []);

  // ── SSE reader ────────────────────────────────────────────────────────────
  async function handleStream(response: Response) {
    if (!response.body) return;

    const reader = response.body.getReader();
    const dec = new TextDecoder();
    let buf = "";

    setError(null);

    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buf += dec.decode(value, { stream: true });
        const lines = buf.split("\n\n");
        buf = lines.pop() ?? "";

        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          const raw = line.slice(6);
          let ev: SSEEvent;
          try {
            ev = JSON.parse(raw) as SSEEvent;
          } catch {
            continue;
          }

          const ts = Date.now();

          // ── Collect in trace ───────────────────────────────────────────
          setTraceEntries((prev) => [...prev, { ts, event: ev }]);

          // ── Update activity feed (skip tokens  -  too noisy) ─────────────
          const item = toActivityItem(ev, ts);
          if (item) {
            setActivityFeed((prev) => [...prev.slice(-7), item]);
          }

          // ── React to event type ────────────────────────────────────────
          if (ev.type === "node_start") {
            // Set streaming stage HERE (not optimistically before resume returns)
            setStreamingStage(ev.stage as Stage);
            setStreamingContent("");
          } else if (ev.type === "token") {
            setStreamingContent((prev) => prev + ev.content);
          } else if (ev.type === "stage_complete") {
            const stage = ev.stage;
            setStreamingStage(stage);
            setStreamingContent("");
            setSessionState((prev) => {
              if (!prev) return prev;
              const patch: Partial<SessionState> = { current_stage: stage };
              const result: StageResult = {
                content: ev.content,
                approved: false,
                edited: false,
              };
              if (stage === "scoping") patch.scope = result;
              if (stage === "solution") patch.solution = result;
              if (stage === "hld") patch.hld = result;
              if (stage === "lld") patch.lld = result;
              return { ...prev, ...patch };
            });
          } else if (ev.type === "awaiting_review") {
            setStreamingStage(null);
            setAwaitingReview(true);
          } else if (ev.type === "session_complete") {
            setIsComplete(true);
            setAwaitingReview(false);
            setStreamingStage(null);
            const currentId = sessionIdRef.current;
            if (currentId) {
              getState(currentId)
                .then((raw) => setSessionState(raw as SessionState))
                .catch(() => null);
            }
          } else if (ev.type === "error") {
            setError(ev.message);
            setStreamingStage(null);
            setIsActing(false);
          } else if (ev.type === "done") {
            setIsActing(false);
            setIsStarting(false);
          }
        }
      }
    } finally {
      setIsActing(false);
      setIsStarting(false);
    }
  }

  // ── Start a new design session ────────────────────────────────────────────
  async function handleStart() {
    if (!requirement.trim() || isStarting) return;

    setIsStarting(true);
    setError(null);
    setStreamingContent("");
    setStreamingStage(null);
    setAwaitingReview(false);
    setIsComplete(false);
    setSessionState(null);
    setTraceEntries([]);
    setActivityFeed([]);

    try {
      const id = await createSession();
      setSessionId(id);
      sessionIdRef.current = id;
      saveSession(id);

      setSessionState({
        session_id: id,
        requirement: requirement.trim(),
        current_stage: "scoping",
        scope: null,
        solution: null,
        hld: null,
        lld: null,
        doc_text: null,
        docx_path: null,
        awaiting_review: false,
      });

      const res = await startSession(id, requirement.trim());
      await handleStream(res);
    } catch (e) {
      setError(String(e));
      setIsStarting(false);
      setStreamingStage(null);
    }
  }

  // ── Approve current stage ─────────────────────────────────────────────────
  async function handleApprove() {
    if (!sessionId || isActing) return;
    setIsActing(true);
    setAwaitingReview(false);
    // NOTE: do NOT set streamingStage here  -  we wait for node_start from backend

    const approvedStage = sessionState?.current_stage;
    if (
      approvedStage &&
      approvedStage !== "doc" &&
      approvedStage !== "complete"
    ) {
      setSessionState((prev) => {
        if (!prev) return prev;
        const result = getResult(prev, approvedStage);
        if (!result) return prev;
        const updated = { ...result, approved: true };
        const patch: Partial<SessionState> = {};
        if (approvedStage === "scoping") patch.scope = updated;
        if (approvedStage === "solution") patch.solution = updated;
        if (approvedStage === "hld") patch.hld = updated;
        if (approvedStage === "lld") patch.lld = updated;
        return { ...prev, ...patch };
      });
    }

    setStreamingContent("");

    try {
      const res = await resumeSession(sessionId, "approve");
      await handleStream(res);
    } catch (e) {
      // Show the real error (e.g. 400 "No stage is currently awaiting review")
      setError(String(e));
      setIsActing(false);
      setStreamingStage(null);
      setAwaitingReview(true); // re-show the review card so user can retry
    }
  }

  // ── Edit and submit current stage content ─────────────────────────────────
  async function handleEdit(content: string) {
    if (!sessionId || isActing) return;
    setIsActing(true);
    setAwaitingReview(false);

    const editedStage = sessionState?.current_stage;
    if (editedStage && editedStage !== "doc" && editedStage !== "complete") {
      setSessionState((prev) => {
        if (!prev) return prev;
        const updated: StageResult = { content, approved: true, edited: true };
        const patch: Partial<SessionState> = {};
        if (editedStage === "scoping") patch.scope = updated;
        if (editedStage === "solution") patch.solution = updated;
        if (editedStage === "hld") patch.hld = updated;
        if (editedStage === "lld") patch.lld = updated;
        return { ...prev, ...patch };
      });
    }

    setStreamingContent("");

    try {
      const res = await resumeSession(sessionId, "edit", content);
      await handleStream(res);
    } catch (e) {
      setError(String(e));
      setIsActing(false);
      setStreamingStage(null);
      setAwaitingReview(true);
    }
  }

  // ── Regenerate from a stage ───────────────────────────────────────────────
  async function handleRegenerate(stage: Stage) {
    if (!sessionId || isActing || isStarting) return;

    const downstream = getDownstreamStages(stage)
      .map((s) => STAGE_LABELS[s])
      .join(", ");

    const confirmed = window.confirm(
      `Regenerating "${STAGE_LABELS[stage]}" will clear: ${downstream}.\n\nContinue?`,
    );
    if (!confirmed) return;

    setIsActing(true);
    setError(null);
    setAwaitingReview(false);
    setIsComplete(false);
    setStreamingContent("");
    setStreamingStage(null); // wait for node_start

    setSessionState((prev) => {
      if (!prev) return prev;
      const stageOrder: Stage[] = ["scoping", "solution", "hld", "lld"];
      const idx = stageOrder.indexOf(stage);
      const patch: Partial<SessionState> = {
        current_stage: stage,
        doc_text: null,
        docx_path: null,
      };
      for (let i = idx; i < stageOrder.length; i++) {
        const s = stageOrder[i];
        if (s === "scoping") patch.scope = null;
        if (s === "solution") patch.solution = null;
        if (s === "hld") patch.hld = null;
        if (s === "lld") patch.lld = null;
      }
      return { ...prev, ...patch };
    });

    try {
      const res = await regenerateFrom(sessionId, stage);
      await handleStream(res);
    } catch (e) {
      setError(String(e));
      setIsActing(false);
      setStreamingStage(null);
    }
  }

  // ── Reset to new session ──────────────────────────────────────────────────
  function handleNewSession() {
    if (abortRef.current) abortRef.current.abort();
    clearSession();
    setSessionId(null);
    sessionIdRef.current = null;
    setSessionState(null);
    setStreamingStage(null);
    setStreamingContent("");
    setAwaitingReview(false);
    setIsComplete(false);
    setRequirement("");
    setError(null);
    setIsActing(false);
    setIsStarting(false);
    setTraceEntries([]);
    setActivityFeed([]);
    setShowTrace(false);
  }

  // ── Derived state ─────────────────────────────────────────────────────────
  const hasSession = !!sessionId && !!sessionState;
  const currentStage = sessionState?.current_stage ?? null;

  const approvedStages = REVIEWABLE_STAGES.filter((s) => {
    const result = getResult(sessionState, s);
    return result?.approved === true && !(awaitingReview && s === currentStage);
  });

  // ── Render ────────────────────────────────────────────────────────────────
  return (
    <div className="flex flex-col min-h-screen">
      {/* ── Header ── */}
      <header className="border-b border-border bg-card/60 backdrop-blur-sm sticky top-0 z-10">
        <div className="max-w-6xl mx-auto px-4 h-12 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <BrainCircuit className="w-4 h-4 text-primary" />
            <span className="font-heading text-[13px] font-semibold text-foreground">
              Architect Bot
            </span>
            <span className="text-[10px] font-medium px-1.5 py-0.5 rounded-full border border-primary/20 bg-primary/10 text-primary ml-1">
              P7
            </span>
          </div>

          <div className="flex items-center gap-3">
            {hasSession && (
              <span className="text-[10px] text-muted-foreground font-mono">
                {sessionId!.slice(0, 8)}
              </span>
            )}
            {hasSession && (
              <>
                <button
                  onClick={() => setShowTrace((v) => !v)}
                  className={`flex items-center gap-1.5 text-[11px] transition-colors px-2 py-1 rounded-md ${
                    showTrace
                      ? "text-primary bg-primary/10"
                      : "text-muted-foreground hover:text-foreground hover:bg-muted/60"
                  }`}
                  title="View full pipeline trace"
                >
                  <GitBranch className="w-3 h-3" />
                  Trace{" "}
                  {traceEntries.length > 0 && (
                    <span className="text-[9px] font-mono">
                      ({traceEntries.length})
                    </span>
                  )}
                </button>

                <button
                  onClick={handleNewSession}
                  title="Start a new design session"
                  className="flex items-center gap-1 text-[11px] text-muted-foreground hover:text-foreground transition-colors"
                >
                  <RotateCcw className="w-3 h-3" />
                  New session
                </button>
              </>
            )}
            <div className="flex items-center gap-1.5 text-[10px] text-muted-foreground">
              <Sparkles className="w-3 h-3" />
              5-stage HITL design
            </div>
          </div>
        </div>
      </header>

      {/* ── Main ── */}
      <main className="flex-1 max-w-6xl mx-auto w-full px-4 py-6">
        {!hasSession ? (
          /* ── Requirement input (no active session) ── */
          <section className="flex flex-col items-center gap-6 mt-10">
            <div className="text-center">
              <h1 className="font-heading text-3xl font-semibold text-foreground">
                Requirement to Design
              </h1>
              <p className="text-sm text-muted-foreground mt-2 max-w-lg mx-auto">
                Paste one paragraph describing what you&apos;re building. Five
                specialist agents will scope, architect, design, and document
                the system - with your review at each stage.
              </p>
            </div>

            <div className="w-full max-w-2xl flex flex-col gap-3">
              <textarea
                value={requirement}
                onChange={(e) => setRequirement(e.target.value)}
                rows={5}
                placeholder="e.g. Build a real-time ride-sharing platform that matches drivers and passengers, handles payments, and scales to 50k concurrent users across mobile and web."
                className="w-full rounded-xl border border-border bg-card px-4 py-3 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary/50 transition-colors resize-none leading-relaxed"
                disabled={isStarting}
              />
              <button
                onClick={handleStart}
                disabled={!requirement.trim() || isStarting}
                className="self-end flex items-center gap-2 px-5 py-2.5 rounded-xl bg-primary text-primary-foreground text-sm font-medium hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed transition-opacity"
              >
                {isStarting ? (
                  <>
                    <span className="btn-spinner" /> Starting…
                  </>
                ) : (
                  <>
                    Start Design <ArrowRight className="w-4 h-4" />
                  </>
                )}
              </button>
            </div>

            {error && (
              <div className="w-full max-w-2xl rounded-xl border border-destructive/30 bg-destructive/5 px-4 py-3 text-[12px] text-destructive">
                {error}
              </div>
            )}
          </section>
        ) : (
          /* ── Active session: sidebar + content ── */
          <div className="grid grid-cols-[280px_1fr] gap-6">
            {/* Left sidebar */}
            <aside className="border-r border-border pr-5 pt-1">
              <div className="mb-4">
                <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground mb-1">
                  Requirement
                </p>
                <p className="text-[11px] text-foreground leading-relaxed line-clamp-4">
                  {sessionState.requirement}
                </p>
              </div>

              <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground mb-2">
                Stages
              </p>
              <StageProgress
                state={sessionState}
                streamingStage={streamingStage}
                awaitingReview={awaitingReview}
                onRegenerate={handleRegenerate}
              />

              {/* Activity feed */}
              {activityFeed.length > 0 && (
                <div className="mt-5 pt-4 border-t border-border">
                  <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground mb-2">
                    Activity
                  </p>
                  <div className="flex flex-col gap-1.5">
                    {activityFeed.map((item, i) => (
                      <div
                        key={i}
                        className={`flex items-center gap-2 text-[10px] ${
                          i === activityFeed.length - 1
                            ? item.color
                            : "text-muted-foreground/60"
                        }`}
                      >
                        <span className="shrink-0">{item.icon}</span>
                        <span className="flex-1 truncate">{item.label}</span>
                        <span className="font-mono shrink-0 text-[9px] opacity-60">
                          {fmtTime(item.ts)}
                        </span>
                      </div>
                    ))}
                  </div>

                  {/* Streaming token counter */}
                  {streamingContent && streamingStage && (
                    <div className="mt-1.5 flex items-center gap-2 text-[10px] text-primary">
                      <span className="wait-spinner" />
                      <span>{streamingContent.length} chars streamed…</span>
                    </div>
                  )}

                  {/* isActing spinner when waiting for node_start */}
                  {isActing && !streamingStage && (
                    <div className="mt-1.5 flex items-center gap-2 text-[10px] text-muted-foreground">
                      <span className="wait-spinner" />
                      <span>Waiting for agent…</span>
                    </div>
                  )}
                </div>
              )}
            </aside>

            {/* Right content */}
            <div className="flex flex-col gap-4 min-w-0">
              {/* Error banner */}
              {error && (
                <div className="rounded-xl border border-destructive/30 bg-destructive/5 px-4 py-3 text-[12px] text-destructive trace-entry">
                  {error}
                </div>
              )}

              {/* Approved stages (collapsed display) */}
              {approvedStages.map((stage) => {
                const result = getResult(sessionState, stage);
                if (!result) return null;
                return (
                  <StageCard
                    key={stage}
                    stage={stage}
                    stageResult={result}
                    isStreaming={false}
                    awaitingReview={false}
                    isApproved={true}
                    onApprove={handleApprove}
                    onEdit={handleEdit}
                    isActing={isActing}
                  />
                );
              })}

              {/* Currently streaming stage */}
              {streamingStage &&
                streamingStage !== "doc" &&
                !awaitingReview &&
                !isComplete && (
                  <div className="rounded-2xl border border-primary/20 bg-card overflow-hidden trace-entry">
                    <div className="flex items-center gap-2 px-4 py-2.5 border-b border-border bg-muted/30">
                      <span className="wait-spinner" />
                      <span className="text-[12px] font-semibold text-primary">
                        {STAGE_LABELS[streamingStage] ?? streamingStage} -
                        generating…
                      </span>
                    </div>
                    <div className="px-4 py-3 max-h-[420px] overflow-y-auto">
                      {streamingContent ? (
                        <div className="md-prose">
                          <ReactMarkdown remarkPlugins={[remarkGfm]}>{streamingContent}</ReactMarkdown>
                          <span className="cursor-blink" />
                        </div>
                      ) : (
                        <div className="flex items-center gap-2 text-[12px] text-muted-foreground py-2">
                          <span className="wait-spinner" />
                          Waiting for first tokens…
                        </div>
                      )}
                    </div>
                  </div>
                )}

              {/* Waiting for next agent to start (post-approve, pre-node_start) */}
              {isActing &&
                !streamingStage &&
                !awaitingReview &&
                !isComplete && (
                  <div className="rounded-2xl border border-border bg-card overflow-hidden trace-entry">
                    <div className="flex items-center gap-2 px-4 py-2.5 border-b border-border bg-muted/30">
                      <span className="wait-spinner" />
                      <span className="text-[12px] font-semibold text-muted-foreground">
                        Starting next agent…
                      </span>
                    </div>
                  </div>
                )}

              {/* Awaiting review */}
              {awaitingReview &&
                currentStage &&
                currentStage !== "complete" && (
                  <StageCard
                    stage={currentStage}
                    stageResult={
                      getResult(sessionState, currentStage) ?? {
                        content: "",
                        approved: false,
                        edited: false,
                      }
                    }
                    isStreaming={false}
                    awaitingReview={true}
                    isApproved={false}
                    onApprove={handleApprove}
                    onEdit={handleEdit}
                    isActing={isActing}
                  />
                )}

              {/* Doc generation in progress */}
              {streamingStage === "doc" && !isComplete && (
                <div className="flex items-center gap-2 text-[12px] text-muted-foreground trace-entry">
                  <span className="wait-spinner" />
                  Assembling final document…
                </div>
              )}

              {/* Complete */}
              {isComplete && sessionState.doc_text && (
                <DocumentPreview
                  docText={sessionState.doc_text}
                  sessionId={sessionId!}
                  onNewSession={handleNewSession}
                />
              )}
            </div>
          </div>
        )}
      </main>

      {/* ── Trace drawer ── */}
      {showTrace && (
        <TraceDrawer
          entries={traceEntries}
          onClose={() => setShowTrace(false)}
        />
      )}
    </div>
  );
}
