'use client'

import { useEffect, useState, useCallback, useRef } from 'react'
import Link from 'next/link'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Separator } from '@/components/ui/separator'
import { SettingsPanel } from '@/components/settings-panel'
import {
  EvalSettings, DEFAULT_EVAL_SETTINGS, NVIDIA_BASE_URL, OLLAMA_BASE_URL,
} from '@/lib/api'
import { ArrowLeft, Play, RotateCw, Square, ChevronDown, Settings2, X } from 'lucide-react'

const SETTINGS_KEY = 'p3-eval-settings'

const NVIDIA_JUDGE_MODELS = [
  { value: 'openai/gpt-oss-20b',                    label: 'gpt-oss-20b  (recommended judge)' },
  { value: 'nvidia/nemotron-3-super-120b-a12b',      label: 'nemotron-3-super-120b  (same as generator)' },
  { value: 'meta/llama-3.2-90b-vision-instruct',     label: 'llama-3.2-90b-vision  (large)' },
  { value: 'meta/llama-3.2-11b-vision-instruct',     label: 'llama-3.2-11b-vision  (lightweight)' },
]
const OLLAMA_JUDGE_MODELS = [
  { value: 'qwen3.5:9b',   label: 'qwen3.5:9b' },
  { value: 'qwen2.5:3b',   label: 'qwen2.5:3b' },
  { value: 'llama3.2:3b',  label: 'llama3.2:3b' },
  { value: 'llama3.1:8b',  label: 'llama3.1:8b' },
]

interface Question {
  id: number
  question: string
  ground_truth: string
  answerable: boolean
  category: string
  answer: string
  contexts: string[]
  context_precision: number | null
  context_recall: number | null
  faithfulness: number | null
  answer_relevancy: number | null
  judge_correctness: number | null
  judge_reasoning: string
  composite: number | null
  classification: string
}

interface Report {
  run_at: string
  eval_model: string
  judge_model: string
  /** Absent on reports written before settings were configurable. */
  config?: {
    prompt_version: string
    top_k_chunks: number
    llm_params?: { temperature?: number }
  }
  aggregates: Record<string, number>
  thresholds: Record<string, number>
  overall_pass: boolean
  per_question: Question[]
}

interface LogLine {
  text: string
  stream: 'stdout' | 'stderr' | 'meta'
}

const METRICS = [
  { key: 'context_precision', label: 'Context precision', thr: 0.7, blurb: 'Share of retrieved chunks that were actually relevant' },
  { key: 'context_recall',    label: 'Context recall',    thr: 0.6, blurb: 'Share of needed information the retriever found' },
  { key: 'faithfulness',      label: 'Faithfulness',      thr: 0.8, blurb: 'Answer claims traceable to the retrieved context' },
  { key: 'answer_relevancy',  label: 'Answer relevancy',  thr: 0.7, blurb: 'How directly the answer addresses the question' },
  { key: 'refusal_accuracy',  label: 'Refusal accuracy',  thr: 0.9, blurb: 'Correct refusals on unanswerable questions' },
]

const fmt = (v: number | null) =>
  v == null || Number.isNaN(v) ? '—' : v.toFixed(3)

function passes(q: Question) {
  if (!q.answerable) return (q.answer ?? '').toLowerCase().includes('could not find')
  return METRICS.slice(0, 4).every(m => {
    const v = q[m.key as keyof Question] as number | null
    return v == null || v >= m.thr
  })
}

// run_eval.py stamps report filenames with datetime.now(timezone.utc), so these
// digits are UTC. Reading them as local time shifted every label by the offset.
function fmtReport(s: string) {
  const m = s.match(/report_(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})(\d{2})/)
  if (!m) return s
  const [, y, mo, d, hh, mm, ss] = m
  const utc = Date.UTC(+y, +mo - 1, +d, +hh, +mm, +ss)
  return new Date(utc).toLocaleString(undefined, {
    day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit', hour12: true,
  })
}

export default function EvalPage() {
  const [reports, setReports]   = useState<string[]>([])
  const [selected, setSelected] = useState('')
  const [report, setReport]     = useState<Report | null>(null)
  const [loading, setLoading]   = useState(true)
  const [error, setError]       = useState('')
  const [selQ, setSelQ]         = useState<number | null>(null)
  const [typeFilter, setTypeFilter]     = useState('all')
  const [statusFilter, setStatusFilter] = useState('all')

  const [settings, setSettings]         = useState<EvalSettings>(DEFAULT_EVAL_SETTINGS)
  const [settingsOpen, setSettingsOpen] = useState(false)
  const [reportKey, setReportKey]       = useState(0)

  const [runOpen, setRunOpen]   = useState(false)
  const [runState, setRunState] = useState<'idle' | 'running' | 'done' | 'failed' | 'stopped'>('idle')
  const [stopping, setStopping] = useState(false)
  const [log, setLog]           = useState<LogLine[]>([])
  const abortRef                = useRef<AbortController | null>(null)
  const stopRequestedRef        = useRef(false)
  const logEndRef               = useRef<HTMLDivElement>(null)

  const loadReports = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const res = await fetch('/api/p3/reports', { cache: 'no-store' })
      const { reports: list } = await res.json()
      if (!list?.length) {
        setError('No evaluation reports yet. Run one to get started.')
        setLoading(false)
        return
      }
      setReports(list)
      setSelected(list[0])
      setReportKey(k => k + 1)
    } catch {
      setError('Could not reach the reports API.')
      setLoading(false)
    }
  }, [])

  useEffect(() => { loadReports() }, [loadReports])

  // A run started before this page loaded (or in another tab) is still the
  // server's business — surface it rather than showing a misleading idle button.
  useEffect(() => {
    fetch('/api/p3/run', { cache: 'no-store' })
      .then(r => r.json())
      .then(({ running }) => {
        if (!running) return
        setRunOpen(true)
        setRunState('running')
        setLog([{ text: 'An evaluation is already running. Output is streaming to whichever tab started it.', stream: 'meta' }])
      })
      .catch(() => {})
  }, [])

  useEffect(() => {
    if (!selected) return
    setLoading(true)
    fetch(`/api/p3/reports?report=${selected}`, { cache: 'no-store' })
      .then(r => r.json())
      .then((data: Report) => {
        setReport(data)
        setSelQ(data.per_question?.[0]?.id ?? null)
        setLoading(false)
      })
      .catch(() => { setError('Failed to read that report file.'); setLoading(false) })
  // reportKey lets Reload force a refetch even when selected hasn't changed.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selected, reportKey])

  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [log])

  // Navigating away stops the stream read only. The evaluation itself keeps
  // running server-side and is picked back up by the status check above.
  useEffect(() => () => abortRef.current?.abort(), [])

  // Settings survive reloads. Read in an effect rather than a lazy useState
  // initialiser so the server and first client render agree.
  useEffect(() => {
    try {
      const saved = localStorage.getItem(SETTINGS_KEY)
      if (saved) setSettings({ ...DEFAULT_EVAL_SETTINGS, ...JSON.parse(saved) })
    } catch {}
  }, [])

  function updateSettings(next: EvalSettings) {
    setSettings(next)
    try { localStorage.setItem(SETTINGS_KEY, JSON.stringify(next)) } catch {}
  }

  async function startRun() {
    if (runState === 'running') return
    setRunOpen(true)
    setRunState('running')
    stopRequestedRef.current = false
    setLog([])

    const ctrl = new AbortController()
    abortRef.current = ctrl

    try {
      const res = await fetch('/api/p3/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ config: settings }),
        signal: ctrl.signal,
      })
      if (!res.ok || !res.body) {
        const { error: msg } = await res.json().catch(() => ({ error: 'Failed to start.' }))
        setLog(l => [...l, { text: msg ?? 'Failed to start.', stream: 'stderr' }])
        setRunState('failed')
        return
      }

      const reader = res.body.getReader()
      const decoder = new TextDecoder()
      let buf = ''

      for (;;) {
        const { done, value } = await reader.read()
        if (done) break
        buf += decoder.decode(value, { stream: true })
        const frames = buf.split('\n\n')
        buf = frames.pop() ?? ''

        for (const frame of frames) {
          const evMatch = frame.match(/^event: (.+)$/m)
          const dataMatch = frame.match(/^data: (.+)$/m)
          if (!evMatch || !dataMatch) continue
          const payload = JSON.parse(dataMatch[1])

          if (evMatch[1] === 'line') {
            setLog(l => [...l, payload as LogLine])
          } else if (evMatch[1] === 'done') {
            const ok = payload.code === 0
            // A killed process also exits non-zero — don't call that a failure.
            if (stopRequestedRef.current) {
              setRunState('stopped')
              setLog(l => [...l, {
                text: 'Evaluation stopped. Progress up to the last completed phase was checkpointed — re-running resumes from there.',
                stream: 'meta',
              }])
            } else {
              setRunState(ok ? 'done' : 'failed')
            }
            if (ok) loadReports()
          }
        }
      }
    } catch (e) {
      if ((e as Error).name !== 'AbortError') setRunState('failed')
    } finally {
      abortRef.current = null
    }
  }

  /**
   * Kills the Python process, not just the stream. run_eval.py checkpoints
   * between phases, so a re-run picks up from the last completed phase.
   */
  async function stopRun() {
    if (stopping) return
    setStopping(true)
    stopRequestedRef.current = true
    setLog(l => [...l, { text: 'Stopping evaluation…', stream: 'meta' }])
    try {
      const res = await fetch('/api/p3/run', { method: 'DELETE' })
      const data = await res.json()
      if (!data.stopped) {
        setLog(l => [...l, { text: data.reason ?? 'Could not stop the run.', stream: 'stderr' }])
      }
      // The stream's own `done` event flips runState when the child exits.
    } catch {
      setLog(l => [...l, { text: 'Stop request failed.', stream: 'stderr' }])
    } finally {
      setStopping(false)
    }
  }

  const allQ       = report?.per_question ?? []
  const answerable = allQ.filter(q => q.answerable)
  const worst5     = [...answerable].sort((a, b) => (a.composite ?? 0) - (b.composite ?? 0)).slice(0, 5)
  const selRow     = allQ.find(q => q.id === selQ) ?? null

  const filtered = allQ.filter(q => {
    if (typeFilter === 'answerable'   && !q.answerable) return false
    if (typeFilter === 'unanswerable' &&  q.answerable) return false
    const p = passes(q)
    if (statusFilter === 'pass' && !p) return false
    if (statusFilter === 'fail' &&  p) return false
    return true
  })

  return (
    <div className="min-h-screen bg-background">
      {/* ── Header ── */}
      <header className="sticky top-0 z-30 h-14 border-b border-border bg-background/85 backdrop-blur-sm">
        <div className="mx-auto flex h-full max-w-6xl items-center gap-4 px-6">
          <Link
            href="/"
            className="flex shrink-0 items-center gap-1.5 text-sm text-muted-foreground transition-colors hover:text-foreground"
          >
            <ArrowLeft className="h-3.5 w-3.5" />
            Chat
          </Link>

          <div className="h-4 w-px shrink-0 bg-border" />

          <div className="flex shrink-0 items-baseline gap-2">
            <span className="font-heading text-base font-semibold tracking-tight">
              Quality Gate
            </span>
            <span className="text-xs text-muted-foreground">· RAG evaluation</span>
          </div>

          <div className="flex-1" />

          {reports.length > 0 && (
            <div className="relative shrink-0">
              <select
                value={selected}
                onChange={e => { setLoading(true); setSelected(e.target.value) }}
                className="h-8 cursor-pointer appearance-none rounded-md border border-border bg-card
                           py-0 pl-3 pr-8 text-xs text-foreground outline-none
                           focus-visible:ring-2 focus-visible:ring-ring/50"
              >
                {reports.map(r => <option key={r} value={r}>{fmtReport(r)}</option>)}
              </select>
              <ChevronDown className="pointer-events-none absolute right-2.5 top-1/2 h-3 w-3 -translate-y-1/2 text-muted-foreground" />
            </div>
          )}

          {/* Hiding the console must not strand it — this brings it back. */}
          {!runOpen && log.length > 0 && (
            <Button
              variant="outline"
              size="sm"
              onClick={() => setRunOpen(true)}
              className="h-8 shrink-0 gap-1.5 px-3 text-xs"
            >
              {runState === 'running' && (
                <span className="h-2 w-2 animate-pulse rounded-full bg-primary" />
              )}
              Console
            </Button>
          )}

          <Button variant="outline" size="sm" onClick={loadReports} className="h-8 shrink-0 gap-1.5 px-3 text-xs">
            <RotateCw className="h-3 w-3" />
            Reload
          </Button>

          <Button
            variant="outline"
            size="sm"
            onClick={() => setSettingsOpen(true)}
            className="h-8 shrink-0 gap-1.5 px-3 text-xs"
          >
            <Settings2 className="h-3 w-3" />
            Settings
          </Button>

          <Button
            size="sm"
            onClick={startRun}
            disabled={runState === 'running'}
            className="h-8 shrink-0 gap-1.5 px-3 text-xs"
          >
            {runState === 'running'
              ? <><span className="h-3 w-3 animate-spin rounded-full border-2 border-primary-foreground/35 border-t-primary-foreground" />Running</>
              : <><Play className="h-3 w-3" />Run evaluation</>}
          </Button>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-6 pb-24 pt-8">

        {/* ── Live console ── visibility is runOpen alone, so Hide always works ── */}
        {runOpen && (
          <section className="mb-8 overflow-hidden rounded-xl border border-border bg-card">
            <div className="flex items-center gap-3 border-b border-border px-5 py-3">
              <span className={
                runState === 'running' ? 'h-2 w-2 animate-pulse rounded-full bg-primary'
                : runState === 'done'  ? 'h-2 w-2 rounded-full bg-primary'
                : runState === 'failed'? 'h-2 w-2 rounded-full bg-destructive'
                :                        'h-2 w-2 rounded-full bg-muted-foreground/40'
              } />
              <span className="font-heading text-sm font-semibold">
                {runState === 'running' ? 'Evaluation in progress'
                  : runState === 'done' ? 'Evaluation complete'
                  : runState === 'failed' ? 'Evaluation failed'
                  : runState === 'stopped' ? 'Evaluation stopped'
                  : 'Console'}
              </span>
              <span className="text-xs text-muted-foreground">
                {runState === 'running' ? 'run_eval.py · this takes several minutes' : `${log.length} lines`}
              </span>

              <div className="flex-1" />

              {runState === 'running' && (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={stopRun}
                  disabled={stopping}
                  className="h-7 gap-1.5 px-2.5 text-xs text-destructive hover:bg-destructive/10 hover:text-destructive"
                >
                  <Square className="h-2.5 w-2.5" />
                  {stopping ? 'Stopping…' : 'Stop evaluation'}
                </Button>
              )}

              <Button
                variant="ghost"
                size="sm"
                onClick={() => setRunOpen(false)}
                className="h-7 px-2.5 text-xs text-muted-foreground"
              >
                Hide
              </Button>
            </div>

            <div className="max-h-80 overflow-y-auto px-5 py-3">
              {log.length === 0 && (
                <p className="py-4 text-xs text-muted-foreground">Waiting for output…</p>
              )}
              {log.map((line, i) => (
                <div
                  key={i}
                  className={`whitespace-pre-wrap break-words font-mono text-xs leading-6 ${
                    line.stream === 'stderr' ? 'text-destructive'
                    : line.stream === 'meta' ? 'text-muted-foreground/70'
                    : 'text-foreground/85'
                  }`}
                >
                  {line.text || ' '}
                </div>
              ))}
              <div ref={logEndRef} />
            </div>
          </section>
        )}

        {/* ── Loading ── */}
        {loading && (
          <div className="flex items-center gap-3 py-24 text-sm text-muted-foreground">
            <span className="h-4 w-4 animate-spin rounded-full border-2 border-border border-t-primary" />
            Loading report…
          </div>
        )}

        {/* ── Empty / error ── */}
        {!loading && error && (
          <div className="rounded-xl border border-border bg-card px-8 py-14 text-center">
            <h2 className="font-heading text-lg font-semibold">{error}</h2>
            <p className="mx-auto mt-2 max-w-md text-sm leading-relaxed text-muted-foreground">
              The evaluation runs 20 questions through the RAG pipeline, scores them with RAGAS
              and an LLM judge, then checks each metric against its release threshold.
            </p>
            <Button onClick={startRun} disabled={runState === 'running'} className="mt-6 gap-2">
              <Play className="h-3.5 w-3.5" />
              Run evaluation
            </Button>
          </div>
        )}

        {/* ── Report ── */}
        {!loading && !error && report && (
          <>
            {/* Verdict */}
            <section className="mb-10">
              <div className="flex flex-wrap items-end justify-between gap-6">
                <div>
                  <p className="text-xs uppercase tracking-wider text-muted-foreground">Release verdict</p>
                  <h1 className={`font-heading text-5xl font-semibold tracking-tight ${
                    report.overall_pass ? 'text-primary' : 'text-destructive'
                  }`}>
                    {report.overall_pass ? 'Ship it' : 'Blocked'}
                  </h1>
                  <p className="mt-2 max-w-lg text-sm leading-relaxed text-muted-foreground">
                    {report.overall_pass
                      ? 'Every metric cleared its threshold on this run.'
                      : `${METRICS.filter(m => (report.aggregates[m.key] ?? 0) < m.thr).length} of ${METRICS.length} metrics fell below threshold. Details below.`}
                  </p>
                </div>

                <dl className="grid grid-cols-2 gap-x-10 gap-y-3 text-sm sm:grid-cols-3">
                  {[
                    ['Questions',  `${answerable.length} of ${allQ.length} answerable`],
                    ['Generator',  report.eval_model.split('/').pop() ?? '—'],
                    ['Judge',      report.judge_model.split('/').pop() ?? '—'],
                    // Older reports predate the config block — omit rather than guess.
                    ...(report.config
                      ? [
                          ['Prompt',      report.config.prompt_version],
                          ['Top-K chunks', String(report.config.top_k_chunks)],
                          ['Temperature', String(report.config.llm_params?.temperature ?? '—')],
                        ] as [string, string][]
                      : []),
                  ].map(([k, v]) => (
                    <div key={k}>
                      <dt className="text-xs text-muted-foreground">{k}</dt>
                      <dd className="mt-0.5 truncate font-medium tabular-nums" title={v}>{v}</dd>
                    </div>
                  ))}
                </dl>
              </div>
            </section>

            {/* Metrics */}
            <section className="mb-12">
              <h2 className="mb-1 font-heading text-lg font-semibold">Metrics</h2>
              <p className="mb-5 text-sm text-muted-foreground">
                The mark on each track is the release threshold.
              </p>

              <div className="divide-y divide-border overflow-hidden rounded-xl border border-border bg-card">
                {METRICS.map(m => {
                  const score = report.aggregates[m.key] ?? 0
                  const ok = score >= m.thr
                  return (
                    <div key={m.key} className="grid grid-cols-[1fr_auto] items-center gap-x-6 gap-y-3 px-5 py-4 sm:grid-cols-[15rem_1fr_5rem]">
                      <div className="min-w-0">
                        <p className="text-sm font-medium">{m.label}</p>
                        <p className="mt-0.5 text-xs leading-relaxed text-muted-foreground">{m.blurb}</p>
                      </div>

                      <div className="order-3 col-span-2 sm:order-none sm:col-span-1">
                        <div className="relative h-1.5 w-full rounded-full bg-muted">
                          <div
                            className={`absolute inset-y-0 left-0 rounded-full ${ok ? 'bg-primary' : 'bg-destructive'}`}
                            style={{ width: `${Math.min(score, 1) * 100}%` }}
                          />
                          <div
                            className="absolute -top-1 h-3.5 w-px bg-foreground/45"
                            style={{ left: `${m.thr * 100}%` }}
                            title={`Threshold ${m.thr.toFixed(2)}`}
                          />
                        </div>
                      </div>

                      <div className="text-right">
                        <span className={`font-heading text-xl font-semibold tabular-nums ${
                          ok ? 'text-foreground' : 'text-destructive'
                        }`}>
                          {score.toFixed(3)}
                        </span>
                        <span className={`ml-2 text-xs font-medium ${ok ? 'text-primary' : 'text-destructive'}`}>
                          {ok ? 'Pass' : 'Fail'}
                        </span>
                      </div>
                    </div>
                  )
                })}
              </div>
            </section>

            {/* Worst performers */}
            {worst5.length > 0 && (
              <section className="mb-12">
                <h2 className="mb-1 font-heading text-lg font-semibold">Weakest answers</h2>
                <p className="mb-5 text-sm text-muted-foreground">
                  Lowest composite score first. Select one to inspect it.
                </p>
                <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                  {worst5.map(q => (
                    <button
                      key={q.id}
                      onClick={() => { setSelQ(q.id); document.getElementById('detail')?.scrollIntoView({ behavior: 'smooth' }) }}
                      className="rounded-xl border border-border bg-card p-4 text-left transition-colors hover:border-foreground/25"
                    >
                      <div className="flex items-baseline justify-between gap-3">
                        <span className="text-xs text-muted-foreground">Q{q.id} · {q.category}</span>
                        <span className="font-heading text-lg font-semibold tabular-nums text-destructive">
                          {Number(q.composite ?? 0).toFixed(3)}
                        </span>
                      </div>
                      <p className="mt-2 line-clamp-2 text-sm leading-relaxed">{q.question}</p>
                      {q.classification && (
                        <p className="mt-2.5 text-xs text-muted-foreground">
                          Root cause · {q.classification}
                        </p>
                      )}
                    </button>
                  ))}
                </div>
              </section>
            )}

            {/* Table */}
            <section className="mb-12">
              <div className="mb-5 flex flex-wrap items-end justify-between gap-4">
                <div>
                  <h2 className="font-heading text-lg font-semibold">All questions</h2>
                  <p className="mt-1 text-sm text-muted-foreground">
                    Showing {filtered.length} of {allQ.length}. Select a row to inspect it.
                  </p>
                </div>
                <div className="flex gap-2">
                  {[
                    { v: typeFilter,   set: setTypeFilter,   opts: [['all','All types'],['answerable','Answerable'],['unanswerable','Unanswerable']] },
                    { v: statusFilter, set: setStatusFilter, opts: [['all','All results'],['pass','Passing'],['fail','Failing']] },
                  ].map(({ v, set, opts }, i) => (
                    <div key={i} className="relative">
                      <select
                        value={v}
                        onChange={e => set(e.target.value)}
                        className="h-8 cursor-pointer appearance-none rounded-md border border-border bg-card py-0 pl-3 pr-8
                                   text-xs outline-none focus-visible:ring-2 focus-visible:ring-ring/50"
                      >
                        {opts.map(([val, lbl]) => <option key={val} value={val}>{lbl}</option>)}
                      </select>
                      <ChevronDown className="pointer-events-none absolute right-2.5 top-1/2 h-3 w-3 -translate-y-1/2 text-muted-foreground" />
                    </div>
                  ))}
                </div>
              </div>

              <div className="overflow-x-auto rounded-xl border border-border bg-card">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-border">
                      {['', 'Question', 'Precision', 'Recall', 'Faithful.', 'Relevancy', 'Composite', 'Result'].map((h, i) => (
                        <th key={i} className={`px-4 py-3 text-xs font-medium text-muted-foreground ${
                          i > 1 ? 'text-right' : 'text-left'
                        } whitespace-nowrap`}>
                          {h}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {filtered.map(q => {
                      const ok = passes(q)
                      const active = q.id === selQ
                      return (
                        <tr
                          key={q.id}
                          onClick={() => setSelQ(q.id)}
                          className={`cursor-pointer transition-colors ${active ? 'bg-muted' : 'hover:bg-muted/50'}`}
                        >
                          <td className="px-4 py-3 text-xs tabular-nums text-muted-foreground">{q.id}</td>
                          <td className="max-w-xs truncate px-4 py-3">{q.question}</td>
                          {[q.context_precision, q.context_recall, q.faithfulness, q.answer_relevancy, q.composite]
                            .map((v, i) => (
                              <td key={i} className="px-4 py-3 text-right tabular-nums text-muted-foreground">
                                {fmt(v)}
                              </td>
                            ))}
                          <td className={`px-4 py-3 text-right text-xs font-medium ${ok ? 'text-primary' : 'text-destructive'}`}>
                            {ok ? 'Pass' : 'Fail'}
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
                {filtered.length === 0 && (
                  <p className="px-5 py-10 text-center text-sm text-muted-foreground">
                    No questions match these filters.
                  </p>
                )}
              </div>
            </section>

            {/* Detail */}
            {selRow && (
              <section id="detail" className="scroll-mt-20">
                <h2 className="mb-1 font-heading text-lg font-semibold">
                  Question {selRow.id}
                </h2>
                <p className="mb-5 text-sm text-muted-foreground">
                  {selRow.category} · {selRow.answerable ? 'answerable' : 'expected refusal'}
                </p>

                <div className="overflow-hidden rounded-xl border border-border bg-card">
                  <div className="border-b border-border px-5 py-4">
                    <p className="text-xs text-muted-foreground">Question</p>
                    <p className="mt-1.5 leading-relaxed">{selRow.question}</p>
                  </div>

                  <div className="grid divide-y divide-border sm:grid-cols-2 sm:divide-x sm:divide-y-0">
                    <div className="px-5 py-4">
                      <p className="text-xs text-muted-foreground">Expected</p>
                      <p className="mt-1.5 text-sm leading-relaxed">{selRow.ground_truth}</p>
                    </div>
                    <div className="px-5 py-4">
                      <p className="text-xs text-muted-foreground">
                        Answered
                        <span className={`ml-2 font-medium ${passes(selRow) ? 'text-primary' : 'text-destructive'}`}>
                          {passes(selRow) ? 'Pass' : 'Fail'}
                        </span>
                      </p>
                      <p className="mt-1.5 text-sm leading-relaxed">{selRow.answer || '—'}</p>
                    </div>
                  </div>

                  {selRow.answerable && (
                    <div className="grid grid-cols-2 divide-x divide-y divide-border border-t border-border sm:grid-cols-5 sm:divide-y-0">
                      {[
                        { lbl: 'Precision',   v: selRow.context_precision, thr: 0.7 },
                        { lbl: 'Recall',      v: selRow.context_recall,    thr: 0.6 },
                        { lbl: 'Faithfulness',v: selRow.faithfulness,      thr: 0.8 },
                        { lbl: 'Relevancy',   v: selRow.answer_relevancy,  thr: 0.7 },
                        { lbl: 'Judge',       v: selRow.judge_correctness, thr: 3, denom: 5 },
                      ].map(({ lbl, v, thr, denom }) => {
                        const val = v == null ? null : Number(v)
                        const ok = val != null && val >= thr
                        return (
                          <div key={lbl} className="px-5 py-4">
                            <p className="text-xs text-muted-foreground">{lbl}</p>
                            <p className={`mt-1 font-heading text-xl font-semibold tabular-nums ${
                              val == null ? 'text-muted-foreground' : ok ? 'text-foreground' : 'text-destructive'
                            }`}>
                              {val == null ? '—' : denom ? `${val}/${denom}` : val.toFixed(3)}
                            </p>
                          </div>
                        )
                      })}
                    </div>
                  )}

                  {selRow.judge_reasoning && (
                    <div className="border-t border-border px-5 py-4">
                      <p className="text-xs text-muted-foreground">Judge reasoning</p>
                      <p className="mt-1.5 text-sm leading-relaxed text-muted-foreground">
                        {selRow.judge_reasoning}
                      </p>
                    </div>
                  )}

                  {(selRow.contexts ?? []).length > 0 && (
                    <details className="group border-t border-border">
                      <summary className="cursor-pointer list-none px-5 py-3.5 text-sm text-muted-foreground transition-colors hover:text-foreground">
                        <span className="inline-flex items-center gap-1.5">
                          <ChevronDown className="h-3.5 w-3.5 transition-transform group-open:rotate-180" />
                          {selRow.contexts.length} retrieved chunks
                        </span>
                      </summary>
                      <div className="space-y-3 px-5 pb-5">
                        {selRow.contexts.map((ctx, i) => (
                          <div key={i} className="rounded-lg bg-muted px-4 py-3">
                            <p className="mb-1.5 text-xs text-muted-foreground">Chunk {i + 1}</p>
                            <p className="text-xs leading-relaxed text-foreground/80">{ctx}</p>
                          </div>
                        ))}
                      </div>
                    </details>
                  )}
                </div>
              </section>
            )}
          </>
        )}
      </main>

      {/* ── Eval settings ── */}
      {settingsOpen && (
        <>
          <div
            className="fixed inset-0 z-40 bg-foreground/10 backdrop-blur-[2px]"
            onClick={() => setSettingsOpen(false)}
          />
          <aside className="fixed inset-y-0 right-0 z-50 flex w-80 flex-col border-l border-border bg-card shadow-xl">
            <div className="flex h-14 shrink-0 items-center justify-between border-b border-border px-5">
              <span className="font-heading text-sm font-semibold">Evaluation settings</span>
              <button
                onClick={() => setSettingsOpen(false)}
                className="flex h-7 w-7 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
                aria-label="Close settings"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            <div className="min-h-0 flex-1 overflow-y-auto">
              <p className="border-b border-border px-5 py-3 text-xs leading-relaxed text-muted-foreground">
                These are sent to P2&rsquo;s <code className="font-mono">/query</code> for every
                question in the dataset, so the eval measures the same configuration the chat uses.
              </p>

              {/* Generator knobs — P2's own panel, so the two cannot drift apart */}
              <SettingsPanel
                settings={settings}
                onChange={(s) => updateSettings({ ...settings, ...s })}
              />

              <Separator />

              <section className="space-y-4 p-5">
                <div>
                  <h3 className="font-heading text-[10px] font-semibold uppercase tracking-[0.1em] text-muted-foreground">
                    Judge
                  </h3>
                  <p className="mt-1.5 text-xs leading-relaxed text-muted-foreground">
                    Scores the answers. Keep this different from the generator — a model
                    grading its own output scores itself generously.
                  </p>
                </div>

                <div className="space-y-2">
                  <Label className="text-xs text-muted-foreground">Judge model</Label>
                  <div className="relative">
                    <select
                      value={settings.judge_model}
                      onChange={(e) => updateSettings({ ...settings, judge_model: e.target.value })}
                      className="h-8 w-full cursor-pointer appearance-none rounded-md border border-border bg-card
                                 py-0 pl-3 pr-8 text-xs text-foreground outline-none
                                 focus-visible:ring-2 focus-visible:ring-ring/50"
                    >
                      {(settings.judge_base_url === OLLAMA_BASE_URL
                        ? OLLAMA_JUDGE_MODELS
                        : NVIDIA_JUDGE_MODELS
                      ).map(m => (
                        <option key={m.value} value={m.value}>{m.label}</option>
                      ))}
                    </select>
                    <ChevronDown className="pointer-events-none absolute right-2.5 top-1/2 h-3 w-3 -translate-y-1/2 text-muted-foreground" />
                  </div>
                </div>

                <div className="space-y-2">
                  <Label className="text-xs text-muted-foreground">Judge endpoint</Label>
                  <Input
                    value={settings.judge_base_url}
                    onChange={(e) => updateSettings({ ...settings, judge_base_url: e.target.value })}
                    className="h-8 font-mono text-xs"
                  />
                  <div className="flex gap-1.5 pt-0.5">
                    {[
                      // Switching endpoint also resets model + reasoning_effort to sane defaults
                      // for that provider, so the two can't get out of sync.
                      { label: 'NVIDIA', url: NVIDIA_BASE_URL, effort: '',     model: NVIDIA_JUDGE_MODELS[0].value },
                      { label: 'Ollama', url: OLLAMA_BASE_URL, effort: 'none', model: OLLAMA_JUDGE_MODELS[0].value },
                    ].map(({ label, url, effort, model }) => (
                      <button
                        key={label}
                        onClick={() => updateSettings({
                          ...settings, judge_base_url: url, judge_reasoning_effort: effort, judge_model: model,
                        })}
                        className={`rounded-md border px-2 py-1 text-[11px] transition-colors ${
                          settings.judge_base_url === url
                            ? 'border-primary bg-primary/10 text-primary'
                            : 'border-border text-muted-foreground hover:text-foreground'
                        }`}
                      >
                        {label}
                      </button>
                    ))}
                  </div>
                  {settings.judge_base_url === OLLAMA_BASE_URL && (
                    <p className="text-xs leading-relaxed text-muted-foreground">
                      Use the exact <code className="font-mono">ollama list</code> tag as the
                      model name. Ollama must be running.
                    </p>
                  )}
                </div>

                <div className="space-y-2">
                  <Label className="text-xs text-muted-foreground">Reasoning effort</Label>
                  <Input
                    value={settings.judge_reasoning_effort}
                    onChange={(e) =>
                      updateSettings({ ...settings, judge_reasoning_effort: e.target.value })
                    }
                    placeholder="blank = provider default"
                    className="h-8 font-mono text-xs"
                  />
                  <p className="text-xs leading-relaxed text-muted-foreground">
                    {settings.judge_reasoning_effort === 'none'
                      ? 'Chain-of-thought off — roughly 40s per judge call on a local CPU instead of several minutes.'
                      : 'Set to none for a local thinking model, or it will spend minutes reasoning on every one of ~84 calls.'}
                  </p>
                </div>

                <div className="rounded-lg bg-muted px-3 py-2.5">
                  <p className="text-xs leading-relaxed text-muted-foreground">
                    Embeddings stay on NVIDIA either way —{' '}
                    <span className="font-mono">answer_relevancy</span> needs a real embedding
                    model, and a local chat model cannot serve that.
                  </p>
                </div>
              </section>

              <Separator />

              <div className="space-y-3 p-5">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => updateSettings(DEFAULT_EVAL_SETTINGS)}
                  className="h-8 w-full text-xs"
                >
                  Reset to defaults
                </Button>
                <p className="text-xs leading-relaxed text-muted-foreground">
                  Changing any generator setting discards the cached checkpoint — the next run
                  re-queries P2 rather than scoring the previous configuration&rsquo;s answers.
                </p>
              </div>
            </div>
          </aside>
        </>
      )}
    </div>
  )
}
