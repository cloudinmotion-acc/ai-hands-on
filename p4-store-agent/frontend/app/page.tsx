"use client";

import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import {
  Brain, Wrench, Eye, CheckCircle2, XCircle,
  Play, RotateCcw, ChevronDown, ChevronRight, Package,
  Zap, AlertTriangle, Tag, Truck, Copy, Clock,
} from "lucide-react";

// ── Types ─────────────────────────────────────────────────────────────────────

type Scenario = {
  id: number;
  label: string;
  description: string;
  request: string;
};

type TraceStep =
  | { type: "thought"; text: string }
  | { type: "tool_call"; tool: string; input: Record<string, unknown>; expanded: boolean }
  | { type: "observation"; tool: string; result: Record<string, unknown>; expanded: boolean }
  | { type: "error"; message: string };

type RunState = "idle" | "running" | "done" | "error";

// ── Constants ─────────────────────────────────────────────────────────────────

const MODELS = [
  { value: "nvidia/nemotron-3-super-120b-a12b", label: "nemotron-120B  (flagship)" },
  { value: "meta/llama-3.2-90b-vision-instruct", label: "llama-90B  (large)" },
  { value: "meta/llama-3.2-11b-vision-instruct", label: "llama-11B  (lightweight)" },
];

// Colours tuned for light background — 400-series is too low contrast on cream
const TOOL_META: Record<string, { icon: React.ReactNode; colorCls: string; bgCls: string; label: string }> = {
  check_stock:  { icon: <Package  className="w-3.5 h-3.5" />, colorCls: "text-amber-700",  bgCls: "bg-amber-500/10",  label: "check_stock"  },
  price_order:  { icon: <Tag      className="w-3.5 h-3.5" />, colorCls: "text-teal-700",   bgCls: "bg-teal-500/10",   label: "price_order"  },
  delivery_eta: { icon: <Truck    className="w-3.5 h-3.5" />, colorCls: "text-violet-700", bgCls: "bg-violet-500/10", label: "delivery_eta" },
};

// ── Helpers ───────────────────────────────────────────────────────────────────

function fmt(v: unknown): string {
  if (v === null || v === undefined) return "—";
  if (typeof v === "boolean") return v ? "Yes" : "No";
  if (typeof v === "number") return v.toLocaleString("en-IN");
  return String(v);
}
function fmtINR(n: number) { return `₹${n.toLocaleString("en-IN")}`; }
function fmtElapsed(ms: number) {
  const s = Math.floor(ms / 1000);
  return s < 60 ? `${s}s` : `${Math.floor(s / 60)}m ${s % 60}s`;
}
function parseError(raw: string): string {
  if (raw.includes("Service temporarily overloaded") || raw.includes("overloaded_error"))
    return "NVIDIA API is temporarily overloaded — the backend will retry automatically. If it keeps failing, wait a minute and try again.";
  if (raw.includes("APIConnectionError") || raw.includes("Connection refused"))
    return "Cannot reach NVIDIA API. Check your connection.";
  if (raw.includes("rate_limit") || raw.includes("429"))
    return "Rate limit reached. Please wait before retrying.";
  return raw.split("\n")[0].slice(0, 200);
}

// ── Sub-components ────────────────────────────────────────────────────────────

function StepBadge({ type, tool }: { type: string; tool?: string }) {
  if (type === "thought")
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold uppercase tracking-wider bg-primary/10 text-primary">
        <Brain className="w-3 h-3" /> Thought
      </span>
    );
  if (type === "tool_call") {
    const m = tool ? TOOL_META[tool] : null;
    return (
      <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold uppercase tracking-wider ${m?.bgCls ?? "bg-amber-500/10"} ${m?.colorCls ?? "text-amber-700"}`}>
        {m?.icon ?? <Wrench className="w-3 h-3" />} {m?.label ?? tool ?? "tool"}
      </span>
    );
  }
  if (type === "observation") {
    const m = tool ? TOOL_META[tool] : null;
    return (
      <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold uppercase tracking-wider ${m?.bgCls ?? "bg-teal-500/10"} ${m?.colorCls ?? "text-teal-700"}`}>
        <Eye className="w-3 h-3" /> Result
      </span>
    );
  }
  return null;
}

function JsonBlock({ data }: { data: Record<string, unknown> }) {
  return (
    <pre className="mt-2 rounded-xl bg-muted border border-border p-3 text-[11px] font-mono text-muted-foreground overflow-x-auto whitespace-pre-wrap">
      {JSON.stringify(data, null, 2)}
    </pre>
  );
}

function ObservationCard({ tool, result }: { tool: string; result: Record<string, unknown> }) {
  if (result.error) {
    return (
      <div className="mt-2 rounded-xl border border-fail/30 bg-fail/10 px-4 py-3 text-sm text-fail">
        <AlertTriangle className="inline w-3.5 h-3.5 mr-1.5" />
        {String(result.error)}
      </div>
    );
  }
  if (tool === "check_stock") {
    const inStock = result.in_stock as boolean;
    return (
      <div className={`mt-2 rounded-xl border px-4 py-3 text-sm ${inStock ? "border-pass/30 bg-pass/10" : "border-fail/30 bg-fail/10"}`}>
        <div className="flex items-center gap-2 mb-1.5">
          {inStock
            ? <CheckCircle2 className="w-4 h-4 text-pass" />
            : <XCircle      className="w-4 h-4 text-fail" />}
          <span className={`font-semibold ${inStock ? "text-pass" : "text-fail"}`}>
            {inStock ? "In stock" : "Out of stock"}
          </span>
        </div>
        <div className="grid grid-cols-2 gap-x-4 gap-y-0.5 text-xs text-muted-foreground">
          <span>SKU: <span className="text-foreground font-mono">{fmt(result.sku)}</span></span>
          <span>Available: <span className="text-foreground">{fmt(result.available)}</span></span>
          <span>Requested: <span className="text-foreground">{fmt(result.requested)}</span></span>
          <span>Unit price: <span className="text-foreground">{fmtINR(result.unit_price as number)}</span></span>
        </div>
      </div>
    );
  }
  if (tool === "price_order") {
    return (
      <div className="mt-2 rounded-xl border border-teal-600/20 bg-teal-500/5 px-4 py-3 text-sm">
        <div className="flex items-center justify-between">
          <span className="text-muted-foreground text-xs">Base total</span>
          <span>{fmtINR(result.base_total as number)}</span>
        </div>
        {(result.discount_percent as number) > 0 && (
          <div className="flex items-center justify-between mt-1">
            <span className="text-muted-foreground text-xs">{String(result.discount_label)}</span>
            <span className="text-pass">−{fmtINR(result.discount_amount as number)} ({result.discount_percent}%)</span>
          </div>
        )}
        <div className="flex items-center justify-between mt-2 pt-2 border-t border-teal-600/20">
          <span className="font-semibold text-teal-700">Final total</span>
          <span className="font-semibold text-teal-700 text-base">{fmtINR(result.final_total as number)}</span>
        </div>
      </div>
    );
  }
  if (tool === "delivery_eta") {
    return (
      <div className="mt-2 rounded-xl border border-violet-600/20 bg-violet-500/5 px-4 py-3 text-sm">
        <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs">
          <span className="text-muted-foreground">Zone</span>      <span>{fmt(result.zone_label)}</span>
          <span className="text-muted-foreground">Shipping</span>  <span className="capitalize">{fmt(result.shipping_type)}</span>
          <span className="text-muted-foreground">Cost</span>      <span>{fmtINR(result.cost as number)}</span>
          <span className="text-muted-foreground">ETA</span>       <span className="font-semibold text-violet-700">{fmt(result.estimated_delivery)}</span>
        </div>
      </div>
    );
  }
  return <JsonBlock data={result} />;
}

function TraceEntry({
  step, index, onToggle, isActiveThought,
}: {
  step: TraceStep;
  index: number;
  onToggle: (i: number) => void;
  isActiveThought?: boolean;
}) {
  if (step.type === "thought") {
    return (
      <div className="flex gap-3 trace-entry">
        <div className="flex flex-col items-center gap-1">
          <div className="w-6 h-6 rounded-full bg-primary/10 border border-primary/20 flex items-center justify-center shrink-0">
            <Brain className="w-3 h-3 text-primary" />
          </div>
          <div className="w-px flex-1 bg-border" />
        </div>
        <div className="pb-4 min-w-0 flex-1">
          <StepBadge type="thought" />
          <p className="mt-2 text-sm text-muted-foreground leading-relaxed whitespace-pre-wrap">
            {step.text}
            {isActiveThought && (
              <span className="inline-block w-0.5 h-3.5 bg-primary ml-0.5 align-middle animate-pulse" />
            )}
          </p>
        </div>
      </div>
    );
  }
  if (step.type === "tool_call") {
    const m = TOOL_META[step.tool] ?? {};
    return (
      <div className="flex gap-3 trace-entry">
        <div className="flex flex-col items-center gap-1">
          <div className={`w-6 h-6 rounded-full ${m.bgCls ?? "bg-amber-500/10"} border border-current/20 flex items-center justify-center shrink-0 ${m.colorCls ?? "text-amber-700"}`}>
            {m.icon ?? <Wrench className="w-3 h-3" />}
          </div>
          <div className="w-px flex-1 bg-border" />
        </div>
        <div className="pb-4 min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <StepBadge type="tool_call" tool={step.tool} />
            <button onClick={() => onToggle(index)} className="text-muted-foreground hover:text-foreground transition-colors">
              {step.expanded ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />}
            </button>
          </div>
          {step.expanded && <JsonBlock data={step.input} />}
        </div>
      </div>
    );
  }
  if (step.type === "observation") {
    const m = TOOL_META[step.tool] ?? {};
    return (
      <div className="flex gap-3 trace-entry">
        <div className="flex flex-col items-center gap-1">
          <div className={`w-6 h-6 rounded-full ${m.bgCls ?? "bg-teal-500/10"} border border-current/20 flex items-center justify-center shrink-0 ${m.colorCls ?? "text-teal-700"}`}>
            <Eye className="w-3 h-3" />
          </div>
          <div className="w-px flex-1 bg-border" />
        </div>
        <div className="pb-4 min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <StepBadge type="observation" tool={step.tool} />
            <button onClick={() => onToggle(index)} className="text-muted-foreground hover:text-foreground transition-colors">
              {step.expanded ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />}
            </button>
          </div>
          <ObservationCard tool={step.tool} result={step.result} />
          {step.expanded && <JsonBlock data={step.result} />}
        </div>
      </div>
    );
  }
  if (step.type === "error") {
    return (
      <div className="flex gap-3 trace-entry">
        <div className="w-6 h-6 rounded-full bg-fail/10 border border-fail/20 flex items-center justify-center shrink-0">
          <AlertTriangle className="w-3 h-3 text-fail" />
        </div>
        <div className="pb-4 min-w-0 flex-1">
          <span className="text-xs font-semibold text-fail uppercase tracking-wider">Error</span>
          <p className="mt-1 text-sm text-fail/80 leading-relaxed">{parseError(step.message)}</p>
        </div>
      </div>
    );
  }
  return null;
}

// ── Main Page ─────────────────────────────────────────────────────────────────

export default function Page() {
  const [scenarios, setScenarios]           = useState<Scenario[]>([]);
  const [request, setRequest]               = useState("");
  const [trace, setTrace]                   = useState<TraceStep[]>([]);
  const [finalAnswer, setFinalAnswer]       = useState("");
  const [runState, setRunState]             = useState<RunState>("idle");
  const [activeScenario, setActiveScenario] = useState<number | null>(null);
  const [model, setModel]                   = useState(MODELS[0].value);
  const [elapsed, setElapsed]               = useState(0);
  const [copied, setCopied]                 = useState(false);
  const [lastRequest, setLastRequest]       = useState("");
  const [answerExpanded, setAnswerExpanded] = useState(false);
  const traceEndRef = useRef<HTMLDivElement>(null);
  const startRef    = useRef<number>(0);

  useEffect(() => {
    fetch("/api/scenarios").then(r => r.json()).then(d => setScenarios(d.scenarios ?? [])).catch(() => {});
  }, []);

  useEffect(() => {
    traceEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [trace]);

  useEffect(() => {
    if (runState !== "running") return;
    startRef.current = Date.now();
    setElapsed(0);
    const id = setInterval(() => setElapsed(Date.now() - startRef.current), 500);
    return () => clearInterval(id);
  }, [runState]);

  function toggleExpand(index: number) {
    setTrace(prev =>
      prev.map((s, i) =>
        i === index && (s.type === "tool_call" || s.type === "observation")
          ? { ...s, expanded: !s.expanded } : s
      )
    );
  }

  function reset() {
    setTrace([]); setFinalAnswer(""); setRunState("idle");
    setActiveScenario(null); setElapsed(0); setCopied(false);
  }

  function copyAnswer() {
    if (!finalAnswer) return;
    navigator.clipboard.writeText(finalAnswer);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  async function runAgent(req: string) {
    if (runState === "running" || !req.trim()) return;
    setTrace([]); setFinalAnswer(""); setCopied(false); setElapsed(0); setAnswerExpanded(false);
    setRunState("running"); setLastRequest(req);

    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ request: req, model }),
      });
      if (!res.ok || !res.body) { setRunState("error"); return; }

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buf = "", capturedAnswer = "";

      for (;;) {
        const { done, value } = await reader.read();
        if (done) break;
        buf += decoder.decode(value, { stream: true });
        const frames = buf.split("\n\n");
        buf = frames.pop() ?? "";

        for (const frame of frames) {
          const evM = frame.match(/^event: (.+)$/m);
          const daM = frame.match(/^data: (.+)$/m);
          if (!evM || !daM) continue;
          const ev = evM[1], payload = JSON.parse(daM[1]);

          if (ev === "thought") {
            setTrace(prev => {
              const last = prev[prev.length - 1];
              if (last?.type === "thought")
                return [...prev.slice(0, -1), { ...last, text: last.text + payload.token }];
              return [...prev, { type: "thought", text: payload.token }];
            });
          } else if (ev === "tool_call") {
            setTrace(prev => [...prev, { type: "tool_call", tool: payload.tool, input: payload.input, expanded: false }]);
          } else if (ev === "observation") {
            setTrace(prev => [...prev, { type: "observation", tool: payload.tool, result: payload.result, expanded: true }]);
          } else if (ev === "answer") {
            capturedAnswer = payload.text;
            setFinalAnswer(payload.text);
          } else if (ev === "error") {
            setTrace(prev => [...prev, { type: "error", message: payload.message }]);
          } else if (ev === "done") {
            if (!capturedAnswer) {
              setTrace(prev => {
                const thoughts = prev.filter(s => s.type === "thought");
                const last = thoughts[thoughts.length - 1];
                if (last?.type === "thought") setFinalAnswer(last.text);
                return prev;
              });
            }
            setRunState(payload.success ? "done" : "error");
          }
        }
      }
    } catch {
      setRunState("error");
    }
  }

  const isRunning = runState === "running";
  const isDone    = runState === "done" || runState === "error";

  const lastThoughtIdx = trace.reduce<number>((acc, s, i) => s.type === "thought" ? i : acc, -1);
  const stockObs    = trace.find(s => s.type === "observation" && s.tool === "check_stock")  as Extract<TraceStep, { type: "observation" }> | undefined;
  const priceObs    = trace.find(s => s.type === "observation" && s.tool === "price_order")  as Extract<TraceStep, { type: "observation" }> | undefined;
  const deliveryObs = trace.find(s => s.type === "observation" && s.tool === "delivery_eta") as Extract<TraceStep, { type: "observation" }> | undefined;
  const errorStep   = trace.find(s => s.type === "error")                                    as Extract<TraceStep, { type: "error" }>       | undefined;

  const showAnswerCard = isDone && (stockObs !== undefined || finalAnswer !== "");
  const showErrorCard  = runState === "error" && !showAnswerCard;

  return (
    <div className="flex flex-col h-dvh bg-background text-foreground">

      {/* ── Header — same structure as P2 ── */}
      <header className="h-14 shrink-0 border-b border-border flex items-center px-5 gap-4">

        <div className="flex items-baseline gap-2 shrink-0">
          <span className="font-heading text-base font-semibold tracking-tight text-foreground">
            Store Assistant Agent
          </span>
          <span className="text-xs text-muted-foreground">· LangGraph ReAct · P4</span>
        </div>

        {/* Model selector */}
        <div className="flex items-center gap-2">
          <span className="text-[10px] uppercase tracking-[0.08em] text-muted-foreground">Model</span>
          <select
            value={model}
            onChange={e => setModel(e.target.value)}
            disabled={isRunning}
            className="h-7 px-2 rounded-md border border-border bg-card text-muted-foreground text-[11px] outline-none disabled:cursor-not-allowed cursor-pointer"
          >
            {MODELS.map(m => <option key={m.value} value={m.value}>{m.label}</option>)}
          </select>
        </div>

        <div className="flex-1" />

        {/* Elapsed */}
        {(isRunning || (isDone && elapsed > 0)) && (
          <div className="flex items-center gap-1.5 text-[11px] text-muted-foreground">
            <Clock className="w-3 h-3" />
            {fmtElapsed(elapsed)}
          </div>
        )}

        {/* Status */}
        <div className="flex items-center gap-1.5 text-[11px] text-muted-foreground">
          <span className={`w-1.5 h-1.5 rounded-full ${
            isRunning              ? "bg-primary animate-pulse"
            : runState === "done"  ? "bg-pass"
            : runState === "error" ? "bg-fail"
            : "bg-border"
          }`} />
          {isRunning ? "Running" : runState === "done" ? "Complete" : runState === "error" ? "Error" : "Idle"}
        </div>

        {/* Reset */}
        {isDone && (
          <button
            onClick={reset}
            className="inline-flex items-center gap-1.5 h-8 px-3 rounded-lg text-xs font-medium text-muted-foreground hover:text-foreground hover:bg-muted border border-border transition-colors cursor-pointer"
          >
            <RotateCcw className="w-3 h-3" /> Reset
          </button>
        )}
      </header>

      {/* ── Body ── */}
      <div className="flex-1 flex min-h-0">

        {/* Left panel */}
        <aside className="w-80 shrink-0 border-r border-border flex flex-col p-5 gap-5 overflow-y-auto">

          <div className="flex flex-col gap-2">
            <label className="text-[10px] font-bold uppercase tracking-[0.1em] text-muted-foreground">Request</label>
            <textarea
              value={request}
              onChange={e => { setRequest(e.target.value); setActiveScenario(null); }}
              placeholder="e.g. 2 blue shirts size M to 560001"
              rows={4}
              disabled={isRunning}
              className="resize-none px-3 py-2.5 rounded-xl border border-border bg-card text-foreground text-sm leading-relaxed outline-none disabled:opacity-60 placeholder:text-muted-foreground font-[inherit] focus:border-primary/50 transition-colors"
            />
            <button
              onClick={() => runAgent(request)}
              disabled={isRunning || !request.trim()}
              className="flex items-center justify-center gap-2 h-9 rounded-xl bg-primary text-primary-foreground font-semibold text-sm disabled:opacity-50 disabled:cursor-not-allowed hover:opacity-90 transition-opacity cursor-pointer"
            >
              {isRunning
                ? <><span className="btn-spinner" />Running…</>
                : <><Play className="w-3.5 h-3.5" />Run Agent</>}
            </button>
          </div>

          <div className="flex items-center gap-2">
            <div className="flex-1 h-px bg-border" />
            <span className="text-[10px] uppercase tracking-[0.1em] text-muted-foreground">or try a scenario</span>
            <div className="flex-1 h-px bg-border" />
          </div>

          <div className="flex flex-col gap-2">
            {scenarios.map(s => (
              <button
                key={s.id}
                disabled={isRunning}
                onClick={() => { setRequest(s.request); setActiveScenario(s.id); runAgent(s.request); }}
                className={`w-full text-left p-3 rounded-xl border transition-colors disabled:opacity-60 disabled:cursor-not-allowed cursor-pointer ${
                  activeScenario === s.id
                    ? "border-primary bg-primary/10"
                    : "border-border bg-card hover:border-primary/40 hover:bg-primary/5"
                }`}
              >
                <div className="flex items-center gap-1.5 mb-1">
                  <span className="w-[18px] h-[18px] rounded-full bg-primary/20 text-primary text-[10px] font-bold flex items-center justify-center shrink-0">
                    {s.id}
                  </span>
                  <span className="font-semibold text-xs text-foreground">{s.label}</span>
                  {s.id === 2 && <Tag           className="w-2.5 h-2.5 text-muted-foreground" />}
                  {s.id === 3 && <XCircle       className="w-2.5 h-2.5 text-fail" />}
                  {s.id === 4 && <AlertTriangle className="w-2.5 h-2.5 text-amber-600" />}
                  {s.id === 5 && <Zap           className="w-2.5 h-2.5 text-muted-foreground" />}
                </div>
                <p className="text-[11px] text-muted-foreground pl-[26px]">{s.description}</p>
              </button>
            ))}
          </div>

          <div className="mt-auto p-3 rounded-xl border border-border bg-card">
            <p className="text-[10px] font-bold uppercase tracking-[0.1em] text-muted-foreground mb-2">ReAct loop</p>
            {[
              { icon: <Brain  className="w-3 h-3" />, cls: "text-primary",    label: "Reason" },
              { icon: <Wrench className="w-3 h-3" />, cls: "text-amber-700",  label: "Act (tool call)" },
              { icon: <Eye    className="w-3 h-3" />, cls: "text-teal-700",   label: "Observe (result)" },
            ].map(({ icon, cls, label }) => (
              <div key={label} className="flex items-center gap-2 mb-1.5 text-[11px] text-muted-foreground">
                <span className={cls}>{icon}</span>{label}
              </div>
            ))}
          </div>
        </aside>

        {/* Right panel */}
        <div className="flex-1 flex flex-col min-w-0 min-h-0">

          <div className="px-6 py-3 border-b border-border flex items-center gap-2 shrink-0">
            <span className="font-semibold text-sm text-foreground">Agent Trace</span>
            {trace.length > 0 && (
              <span className="px-2 py-0.5 rounded-full text-[11px] bg-muted text-muted-foreground">
                {trace.length} steps
              </span>
            )}
          </div>

          <div className="flex-1 overflow-y-auto px-6 py-5">
            {trace.length === 0 && !isRunning && (
              <div className="flex flex-col items-center justify-center h-full gap-3 text-center">
                <div className="w-12 h-12 rounded-2xl bg-primary/10 flex items-center justify-center">
                  <Brain className="w-5 h-5 text-primary" />
                </div>
                <p className="text-sm text-muted-foreground max-w-[280px] leading-relaxed">
                  Run a request to watch the agent reason → call tools → observe results in real-time.
                </p>
              </div>
            )}

            {isRunning && trace.length === 0 && (
              <div className="flex items-center gap-2.5 text-sm text-muted-foreground">
                <span className="wait-spinner" /> Waiting for agent…
              </div>
            )}

            {trace.map((step, i) => (
              <TraceEntry
                key={i} step={step} index={i}
                onToggle={toggleExpand}
                isActiveThought={isRunning && i === lastThoughtIdx}
              />
            ))}
            <div ref={traceEndRef} />
          </div>

          {/* ── Answer card ── */}
          {showAnswerCard && (
            <div className="border-t border-border px-6 py-4 shrink-0 bg-card">
              {stockObs && (
                (stockObs.result.in_stock === false || stockObs.result.error) ? (
                  <div className="flex items-center gap-2.5">
                    <XCircle className="w-5 h-5 text-fail shrink-0" />
                    <div>
                      <p className="font-semibold text-fail">Out of stock</p>
                      <p className="text-xs text-muted-foreground mt-0.5">
                        {stockObs.result.error
                          ? String(stockObs.result.error)
                          : `Only ${stockObs.result.available} units available (${stockObs.result.requested} requested)`}
                      </p>
                    </div>
                  </div>
                ) : (
                  <div className="flex items-center flex-wrap gap-5">
                    <div className="flex items-center gap-2">
                      <CheckCircle2 className="w-5 h-5 text-pass shrink-0" />
                      <div>
                        <p className="text-[10px] text-muted-foreground uppercase tracking-[0.08em]">In stock</p>
                        <p className="font-semibold text-pass">{fmt(stockObs.result.available)} available</p>
                      </div>
                    </div>
                    {priceObs && !priceObs.result.error && (
                      <div>
                        <p className="text-[10px] text-muted-foreground uppercase tracking-[0.08em]">Total</p>
                        <p className="font-bold text-base text-foreground">
                          {fmtINR(priceObs.result.final_total as number)}
                          {(priceObs.result.discount_percent as number) > 0 && (
                            <span className="text-[11px] font-normal text-pass ml-1.5">
                              {priceObs.result.discount_percent}% off
                            </span>
                          )}
                        </p>
                      </div>
                    )}
                    {deliveryObs && !deliveryObs.result.error && (
                      <div>
                        <p className="text-[10px] text-muted-foreground uppercase tracking-[0.08em]">Arrives by</p>
                        <p className="font-semibold text-foreground">{fmt(deliveryObs.result.estimated_delivery)}</p>
                        <p className="text-[11px] text-muted-foreground">
                          {fmt(deliveryObs.result.zone_label)} · {fmtINR(deliveryObs.result.cost as number)} shipping
                        </p>
                      </div>
                    )}
                    {deliveryObs?.result.error && (
                      <div className="flex items-center gap-1.5">
                        <AlertTriangle className="w-4 h-4 text-amber-600" />
                        <span className="text-xs text-amber-700">Delivery unavailable: {String(deliveryObs.result.error)}</span>
                      </div>
                    )}
                  </div>
                )
              )}

              {finalAnswer && (
                <div className={stockObs ? "mt-3 pt-3 border-t border-border" : ""}>
                  {/* Toggle row */}
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => setAnswerExpanded(v => !v)}
                      className="inline-flex items-center gap-1.5 h-7 px-2.5 rounded-lg border border-border bg-muted/50 text-[11px] font-medium text-muted-foreground hover:text-foreground hover:bg-muted transition-colors cursor-pointer"
                    >
                      {answerExpanded
                        ? <><ChevronDown className="w-3 h-3" /> Hide answer</>
                        : <><ChevronRight className="w-3 h-3" /> View full answer</>}
                    </button>
                    <button
                      onClick={copyAnswer}
                      className={`inline-flex items-center gap-1 h-7 px-2.5 rounded-lg border text-[11px] font-medium transition-colors cursor-pointer ${
                        copied
                          ? "text-pass border-pass/30 bg-pass/5"
                          : "text-muted-foreground border-border hover:text-foreground hover:bg-muted"
                      }`}
                    >
                      <Copy className="w-3 h-3" />
                      {copied ? "Copied" : "Copy"}
                    </button>
                  </div>
                  {/* Collapsible markdown body */}
                  {answerExpanded && (
                    <div className="mt-2.5 md-prose max-h-56 overflow-y-auto pr-1">
                      <ReactMarkdown>{finalAnswer}</ReactMarkdown>
                    </div>
                  )}
                </div>
              )}

              {runState === "error" && (
                <div className="mt-3 flex justify-end">
                  <button
                    onClick={() => runAgent(lastRequest)}
                    className="inline-flex items-center gap-1.5 h-8 px-3 rounded-lg border border-primary/30 bg-primary/10 text-primary text-xs font-semibold hover:bg-primary/20 transition-colors cursor-pointer"
                  >
                    <RotateCcw className="w-3 h-3" /> Retry
                  </button>
                </div>
              )}
            </div>
          )}

          {/* Pure error card */}
          {showErrorCard && (
            <div className="border-t border-border px-6 py-4 shrink-0 bg-card flex items-center gap-3">
              <AlertTriangle className="w-4 h-4 text-fail shrink-0" />
              <span className="text-sm text-fail flex-1">
                {errorStep ? parseError(errorStep.message) : "Agent failed. Retry or wait a moment."}
              </span>
              <button
                onClick={() => runAgent(lastRequest)}
                className="inline-flex items-center gap-1.5 h-8 px-3 rounded-lg border border-primary/30 bg-primary/10 text-primary text-xs font-semibold hover:bg-primary/20 transition-colors cursor-pointer shrink-0"
              >
                <RotateCcw className="w-3 h-3" /> Retry
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
