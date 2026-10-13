"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  Play, RefreshCw, Zap, CheckCircle2, GitBranch,
  BarChart3, AlertCircle, Sun, Moon,
} from "lucide-react";
import type { EvalResults, EvalEvent, ProgressItem } from "@/lib/types";
import { fetchResults, streamEval } from "@/lib/api";
import { VerdictBanner } from "@/components/VerdictBanner";
import { MetricCard } from "@/components/MetricCard";
import { ScenarioTable } from "@/components/ScenarioTable";
import { PropagationCard } from "@/components/PropagationCard";
import { EvalProgress } from "@/components/EvalProgress";

const STAGES = ["scoping", "solution", "hld", "lld"] as const;

const STAGE_COLORS: Record<string, string> = {
  scoping:  "text-stage-scoping",
  solution: "text-stage-solution",
  hld:      "text-stage-hld",
  lld:      "text-stage-lld",
};

export default function EvalDashboard() {
  const [results, setResults] = useState<EvalResults | null>(null);
  const [loading, setLoading] = useState(true);
  const [isRunning, setIsRunning] = useState(false);
  const [quickMode, setQuickMode] = useState(false);
  const [progress, setProgress] = useState<ProgressItem[]>([]);
  const [phase, setPhase] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isDark, setIsDark] = useState(false);
  const progressIdRef = useRef(0);
  const scenarioProgressIds = useRef<Map<number, string>>(new Map());

  // Sync dark mode from localStorage on mount
  useEffect(() => {
    const saved = localStorage.getItem("p8-theme");
    if (saved === "dark") setIsDark(true);
  }, []);

  const toggleTheme = useCallback(() => {
    const next = !isDark;
    setIsDark(next);
    if (next) {
      document.documentElement.classList.add("dark");
      localStorage.setItem("p8-theme", "dark");
    } else {
      document.documentElement.classList.remove("dark");
      localStorage.setItem("p8-theme", "light");
    }
  }, [isDark]);

  const loadResults = useCallback(async () => {
    try {
      const r = await fetchResults();
      setResults(r);
    } catch {
      setResults(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadResults();
  }, [loadResults]);

  const addProgress = useCallback((text: string, status: ProgressItem["status"]) => {
    const id = String(progressIdRef.current++);
    setProgress((prev) => [...prev.slice(-80), { id, text, status, ts: Date.now() }]);
    return id;
  }, []);

  const updateProgress = useCallback((id: string, status: ProgressItem["status"], text?: string) => {
    setProgress((prev) =>
      prev.map((p) =>
        p.id === id ? { ...p, status, ...(text ? { text } : {}) } : p
      )
    );
  }, []);

  const handleRunEval = useCallback(async () => {
    setIsRunning(true);
    setError(null);
    setProgress([]);
    setPhase("Starting evaluation pipeline…");
    progressIdRef.current = 0;
    scenarioProgressIds.current.clear();

    const onEvent = (event: EvalEvent) => {
      if (event.type === "eval_start") {
        setPhase(
          `Running ${event.scenarios_count} scenarios${event.quick ? " (quick mode)" : ""}…`
        );
        addProgress(
          `Eval started — ${event.scenarios_count} scenarios, concurrency 3`,
          "info"
        );
      } else if (event.type === "scenario_start") {
        setPhase(`[${event.index}/${event.total}] Running scenario ${event.id}: ${event.title}`);
        const pid = addProgress(
          `[${event.index}/${event.total}] ${event.title}…`,
          "running"
        );
        scenarioProgressIds.current.set(event.id, pid);
      } else if (event.type === "scenario_done") {
        const pid = scenarioProgressIds.current.get(event.id);
        if (pid) {
          const pass = event.trajectory?.pass;
          updateProgress(
            pid,
            pass ? "pass" : "fail",
            `${event.title} — trajectory ${pass ? "PASS" : "FAIL"}`
          );
        }
      } else if (event.type === "completeness_start") {
        setPhase("Running LLM completeness judge…");
        const compPid = addProgress("Completeness eval — LLM judging all stage outputs…", "running");
        scenarioProgressIds.current.set(-1, compPid);
      } else if (event.type === "completeness_done") {
        const compPid = scenarioProgressIds.current.get(-1);
        if (compPid) updateProgress(compPid, "info", `Completeness mean: ${(event.mean * 100).toFixed(0)}%`);
      } else if (event.type === "propagation_start") {
        setPhase("Running propagation test…");
        const propPid = addProgress("Propagation test — injecting HITL edit into scoping…", "running");
        scenarioProgressIds.current.set(-2, propPid);
      } else if (event.type === "propagation_done") {
        const propPid = scenarioProgressIds.current.get(-2);
        const text = `Propagation: ${event.pass ? "edit propagated to HLD ✓" : "edit lost — HLD did not reflect change ✗"}`;
        if (propPid) updateProgress(propPid, event.pass ? "pass" : "fail", text);
        else addProgress(text, event.pass ? "pass" : "fail");
      } else if (event.type === "scorecard_ready") {
        setPhase("Scorecard ready");
        setResults(event.result);
        addProgress(`Verdict: ${event.verdict}`, event.verdict === "GO" ? "pass" : "fail");
      } else if (event.type === "error") {
        setError(event.message);
        addProgress(`Error: ${event.message}`, "fail");
      }
    };

    await streamEval(
      { quick: quickMode },
      onEvent,
      () => {
        setIsRunning(false);
        setPhase("Evaluation complete");
      },
      (msg) => {
        setIsRunning(false);
        setError(msg);
        addProgress(`Failed: ${msg}`, "fail");
      }
    );
  }, [quickMode, addProgress, updateProgress]);

  // The completeness gate is applied to the WORST stage, not the mean — so the
  // card must headline the min, or it shows a passing number labelled "fail".
  // Falls back to computing it for reports written before `min` was exported.
  const stageScore = (r: EvalResults, s: (typeof STAGES)[number]) => {
    const d = r.completeness[s];
    return typeof d === "object" ? d.score : 0;
  };
  const compMin = results
    ? results.completeness.min ?? Math.min(...STAGES.map((s) => stageScore(results, s)))
    : 0;
  const compMinStage = results
    ? results.completeness.min_stage ??
      STAGES.reduce((worst, s) =>
        stageScore(results, s) < stageScore(results, worst) ? s : worst
      )
    : "";

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="sticky top-0 z-20 border-b border-border bg-background/90 backdrop-blur-sm">
        <div className="max-w-6xl mx-auto px-4 h-12 flex items-center gap-3">
          <div className="flex items-center gap-2 font-mono text-[13px] font-semibold text-foreground">
            <BarChart3 className="w-4 h-4 text-primary" strokeWidth={2} />
            P8 · Eval Harness
          </div>

          <span className="text-border mx-1">|</span>
          <span className="text-[11px] text-muted-foreground">
            P7 Architect Bot · Quality Gate
          </span>

          <div className="ml-auto flex items-center gap-2">
            {/* Theme toggle */}
            <button
              onClick={toggleTheme}
              aria-label="Toggle theme"
              className="flex items-center justify-center w-7 h-7 rounded-md border border-border bg-surface text-muted-foreground hover:text-foreground hover:border-primary/30 transition-colors"
            >
              {isDark ? <Sun className="w-3.5 h-3.5" /> : <Moon className="w-3.5 h-3.5" />}
            </button>

            {/* Quick mode toggle */}
            <button
              onClick={() => setQuickMode((v) => !v)}
              disabled={isRunning}
              className={`flex items-center gap-1.5 px-2.5 py-1 rounded-md text-[11px] font-medium border transition-colors ${
                quickMode
                  ? "bg-warn-dim border-warn/30 text-warn"
                  : "bg-surface border-border text-muted-foreground hover:text-foreground"
              }`}
            >
              <Zap className="w-3 h-3" />
              Quick {quickMode ? "ON" : "OFF"}
            </button>

            {/* Refresh results */}
            <button
              onClick={loadResults}
              disabled={isRunning}
              className="flex items-center gap-1.5 px-2.5 py-1 rounded-md text-[11px] font-medium border border-border bg-surface text-muted-foreground hover:text-foreground transition-colors disabled:opacity-40"
            >
              <RefreshCw className="w-3 h-3" />
              Refresh
            </button>

            {/* Run eval */}
            <button
              onClick={handleRunEval}
              disabled={isRunning}
              className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg bg-primary text-primary-foreground text-[12px] font-semibold hover:opacity-90 disabled:opacity-50 transition-opacity"
            >
              {isRunning ? (
                <>
                  <span className="btn-spinner" /> Running…
                </>
              ) : (
                <>
                  <Play className="w-3.5 h-3.5" fill="currentColor" />
                  Run Eval{quickMode ? " (quick)" : ""}
                </>
              )}
            </button>
          </div>
        </div>
      </header>

      <main className="max-w-6xl mx-auto px-4 py-6 space-y-5">
        {/* Error */}
        {error && (
          <div className="flex items-start gap-2 rounded-xl border border-nogo/30 bg-nogo-dim px-4 py-3 text-[12px] text-nogo">
            <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
            <span>{error}</span>
          </div>
        )}

        {/* Progress feed (visible while running) */}
        {(isRunning || progress.length > 0) && (
          <EvalProgress items={progress} isRunning={isRunning} phase={phase} />
        )}

        {/* Loading skeleton */}
        {loading && !isRunning && (
          <div className="space-y-4">
            <div className="rounded-2xl h-28 shimmer-row" />
            <div className="grid grid-cols-4 gap-3">
              {[0, 1, 2, 3].map((i) => (
                <div key={i} className="rounded-xl h-28 shimmer-row" />
              ))}
            </div>
          </div>
        )}

        {/* No results state */}
        {!loading && !results && !isRunning && (
          <div className="rounded-2xl border border-border bg-surface text-center py-16 px-8">
            <BarChart3 className="w-10 h-10 text-muted-foreground/40 mx-auto mb-4" strokeWidth={1.5} />
            <h2 className="text-[15px] font-semibold text-foreground mb-2">No evaluation results yet</h2>
            <p className="text-[12px] text-muted-foreground max-w-xs mx-auto mb-6">
              Click <strong>Run Eval</strong> to start the pipeline, or run{" "}
              <code className="font-mono">python run_eval.py</code> from the backend directory.
            </p>
            <p className="text-[11px] text-muted-foreground font-mono mb-1">
              Quick mode (3 scenarios) — recommended for first run:
            </p>
            <code className="text-[11px] font-mono text-primary">
              python run_eval.py --quick
            </code>
          </div>
        )}

        {/* Results */}
        {results && !loading && (
          <>
            {/* Verdict banner */}
            <VerdictBanner results={results} />

            {/* Metrics strip */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              <MetricCard
                label="Trajectory"
                value={`${results.trajectory.passed}/${results.trajectory.total}`}
                sub="scenarios"
                pass={results.trajectory.pass}
                bar={results.trajectory.score}
                threshold={results.trajectory.threshold}
                icon={<CheckCircle2 className="w-3.5 h-3.5" />}
              />
              <MetricCard
                label="Completeness"
                value={`${Math.round(compMin * 100)}%`}
                sub={`worst stage · ${compMinStage}`}
                pass={results.completeness.pass}
                bar={compMin}
                threshold={results.completeness.threshold}
                icon={<BarChart3 className="w-3.5 h-3.5" />}
              />
              <MetricCard
                label="Propagation"
                value={results.propagation.pass === null ? "—" : results.propagation.pass ? "PASS" : "FAIL"}
                sub={results.propagation.error === "skipped" ? "skipped" : `"${results.propagation.search_term}" in ${results.propagation.check_stage}`}
                pass={results.propagation.error === "skipped" ? null : results.propagation.pass}
                icon={<GitBranch className="w-3.5 h-3.5" />}
              />
              <MetricCard
                label="Runtime"
                value={`${(results.duration_s / 60).toFixed(1)}`}
                sub="minutes total"
                pass={null}
                icon={<Zap className="w-3.5 h-3.5" />}
              />
            </div>

            {/* Stage completeness breakdown */}
            <div className="rounded-xl border border-border bg-surface overflow-hidden">
              <div className="px-4 py-3 border-b border-border">
                <h2 className="text-[13px] font-semibold text-foreground">
                  Completeness by Stage
                </h2>
                <p className="text-[11px] text-muted-foreground mt-0.5">
                  LLM judge score, averaged across all scenarios · mean{" "}
                  {Math.round(results.completeness.mean * 100)}% · gate requires{" "}
                  <strong className="text-foreground/70">every</strong> stage ≥{" "}
                  {Math.round(results.completeness.threshold * 100)}%
                </p>
              </div>
              <div className="grid grid-cols-2 sm:grid-cols-4 divide-x divide-border">
                {STAGES.map((stage) => {
                  const data = results.completeness[stage];
                  const score = typeof data === "object" ? data.score : 0;
                  const pct = Math.round(score * 100);
                  const pass = score >= 0.70;
                  return (
                    <div key={stage} className="px-4 py-4 flex flex-col gap-2">
                      <span className={`text-[10px] font-semibold uppercase tracking-wider ${STAGE_COLORS[stage]}`}>
                        {stage}
                      </span>
                      <span className={`font-mono text-[22px] font-semibold leading-none ${pass ? "text-go" : "text-nogo"}`}>
                        {pct}%
                      </span>
                      <div className="score-bar">
                        <div
                          className={`score-bar-fill ${pass ? "bg-go" : "bg-nogo"}`}
                          style={{ width: `${pct}%` }}
                        />
                      </div>
                      <span className={`chip ${pass ? "chip-pass" : "chip-fail"} self-start`}>
                        {pass ? "pass" : "fail"}
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Scenario table */}
            <ScenarioTable results={results} />

            {/* Propagation card */}
            <PropagationCard propagation={results.propagation} />

            {/* Footer note */}
            <p className="text-[11px] text-muted-foreground text-center pb-4">
              Run ID: <span className="font-mono">{results.run_id}</span>
              {" · "}Results saved to <code className="font-mono">results/latest.json</code>
            </p>
          </>
        )}
      </main>
    </div>
  );
}
