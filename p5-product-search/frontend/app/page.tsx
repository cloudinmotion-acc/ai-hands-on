"use client";

import { useState, useRef } from "react";
import ReactMarkdown from "react-markdown";
import {
  Search,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Tag,
  Layers,
  Zap,
  Database,
  Cpu,
  Package,
  Sparkles,
  AlertTriangle,
  Shield,
  ShieldAlert,
  ShieldCheck,
  ExternalLink,
} from "lucide-react";

// ── Types ────────────────────────────────────────────────────────────────────

type TraceEvent =
  | { type: "tool_call"; tool: string; args: Record<string, unknown> }
  | {
      type: "tool_result";
      tool: string;
      decomposed?: { semantic_query: string; filters: Record<string, unknown> };
      result_count?: number;
      top_results?: Product[];
    }
  | { type: "final_answer"; content: string }
  | { type: "error"; message: string }
  | { type: "guard_info"; guard: string; action: "rewrite"; reason: string }
  | { type: "guard_blocked"; guard: string; reason: string };

interface Product {
  id: number;
  name: string;
  category: string;
  gender: string;
  colour: string;
  size: string;
  min_age: number;
  max_age: number;
  price: number;
  fabric: string;
  in_stock: boolean;
  description: string;
  rrf_score?: number;
  similarity?: number;
  bm25_score?: number;
}

const EXAMPLE_QUERIES = [
  "white cotton dress for girls under ₹500",
  "denim jacket for teenage boys",
  "comfortable yoga pants for women in stock",
  "lion print t-shirt for kids",
  "silk blouse for women under ₹800",
];

// ── Mismatch detection ────────────────────────────────────────────────────────

function computeMismatches(
  product: Product,
  filters: Record<string, unknown>,
): Set<string> {
  const mismatches = new Set<string>();
  const s = (v: unknown) => String(v).toLowerCase();

  if (filters.colour && s(product.colour) !== s(filters.colour))
    mismatches.add("colour");

  if (filters.fabric && s(product.fabric) !== s(filters.fabric))
    mismatches.add("fabric");

  if (filters.gender) {
    const pg = s(product.gender);
    if (pg !== s(filters.gender) && pg !== "unisex") mismatches.add("gender");
  }

  if (
    typeof filters.max_price === "number" &&
    product.price > filters.max_price
  )
    mismatches.add("price");

  if (filters.in_stock === true && !product.in_stock) mismatches.add("stock");

  return mismatches;
}

// ── Helper components ─────────────────────────────────────────────────────────

function FilterBadge({ label, value }: { label: string; value: unknown }) {
  return (
    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium bg-primary/10 text-primary border border-primary/20">
      <Tag className="w-2.5 h-2.5" />
      {label}: {String(value)}
    </span>
  );
}

function AttrBadge({
  value,
  mismatch,
  tooltip,
}: {
  value: string;
  mismatch: boolean;
  tooltip?: string;
}) {
  return mismatch ? (
    <span
      title={tooltip}
      className="inline-flex items-center gap-0.5 text-[10px] px-1.5 py-0.5 rounded bg-amber-50 border border-amber-200 text-amber-700 font-medium cursor-default"
    >
      <AlertTriangle className="w-2.5 h-2.5 shrink-0" />
      {value}
    </span>
  ) : (
    <span className="text-[10px] px-1.5 py-0.5 rounded bg-muted border border-border text-muted-foreground">
      {value}
    </span>
  );
}

function ProductCard({
  product,
  filters = {},
}: {
  product: Product;
  filters?: Record<string, unknown>;
}) {
  const mm = computeMismatches(product, filters);
  const stockMismatch = mm.has("stock");
  const priceMismatch = mm.has("price");
  const hasFilters = Object.keys(filters).length > 0;
  const isExact = hasFilters && mm.size === 0;

  return (
    <div
      className={`rounded-xl border p-3.5 flex flex-col gap-1.5 transition-colors ${
        isExact
          ? "border-violet-300 bg-violet-50/60 hover:border-violet-400"
          : "border-border bg-card hover:border-primary/30"
      }`}
    >
      {isExact && (
        <div className="flex items-center gap-1 text-[9px] font-semibold text-violet-600 uppercase tracking-wider -mb-0.5">
          <span className="w-1.5 h-1.5 rounded-full bg-violet-500 shrink-0" />
          Exact match
        </div>
      )}
      <div className="flex items-start justify-between gap-2">
        <p className="text-[13px] font-semibold leading-tight text-foreground">
          {product.name}
        </p>
        <span
          className={`shrink-0 text-[10px] font-semibold px-1.5 py-0.5 rounded-full ${
            stockMismatch
              ? "bg-amber-50 text-amber-700 border border-amber-200"
              : product.in_stock
                ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                : "bg-rose-50 text-rose-700 border border-rose-200"
          }`}
        >
          {stockMismatch && (
            <AlertTriangle className="w-2.5 h-2.5 inline mr-0.5" />
          )}
          {product.in_stock ? "In stock" : "Out of stock"}
        </span>
      </div>

      <p className="text-[11px] text-muted-foreground leading-relaxed line-clamp-2">
        {product.description}
      </p>

      <div className="flex flex-wrap gap-1 mt-0.5">
        <AttrBadge
          value={product.colour}
          mismatch={mm.has("colour")}
          tooltip={`You searched for: ${filters.colour}`}
        />
        <AttrBadge
          value={product.fabric}
          mismatch={mm.has("fabric")}
          tooltip={`You searched for: ${filters.fabric}`}
        />
        <AttrBadge value={`Size ${product.size}`} mismatch={false} />
        <AttrBadge
          value={product.gender}
          mismatch={mm.has("gender")}
          tooltip={`You searched for: ${filters.gender}`}
        />
      </div>

      <div className="flex items-center justify-between mt-1">
        <span
          title={
            priceMismatch ? `Over your ₹${filters.max_price} budget` : undefined
          }
          className={`text-[15px] font-bold flex items-center gap-1 ${
            priceMismatch ? "text-amber-600" : "text-primary"
          }`}
        >
          {priceMismatch && <AlertTriangle className="w-3 h-3 shrink-0" />}₹
          {product.price}
        </span>
        {product.rrf_score !== undefined && (
          <span className="text-[10px] text-muted-foreground font-mono">
            rrf {product.rrf_score.toFixed(4)}
          </span>
        )}
      </div>
    </div>
  );
}

// ── Guard label helpers ────────────────────────────────────────────────────────

function guardLabel(guard: string): string {
  const labels: Record<string, string> = {
    pii_detector: "PII detector",
    injection_detector: "Injection detector",
    topic_filter: "Topic filter",
    input_guard: "Input guard",
    output_guard: "Output guard",
  };
  return labels[guard] ?? guard;
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function Home() {
  const [query, setQuery] = useState("");
  const [running, setRunning] = useState(false);
  const [trace, setTrace] = useState<TraceEvent[]>([]);
  const [finalAnswer, setFinalAnswer] = useState("");
  const [answerExpanded, setAnswerExpanded] = useState(false);
  const [products, setProducts] = useState<Product[]>([]);
  const [decomposed, setDecomposed] = useState<{
    semantic_query: string;
    filters: Record<string, unknown>;
  } | null>(null);
  const [guardMode, setGuardMode] = useState(false);
  const [blocked, setBlocked] = useState<{
    guard: string;
    reason: string;
  } | null>(null);
  const [langsmithUrl, setLangsmithUrl] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  async function runSearch(q?: string) {
    const searchQuery = q ?? query;
    if (!searchQuery.trim() || running) return;

    if (abortRef.current) abortRef.current.abort();
    abortRef.current = new AbortController();

    const apiBase = guardMode
      ? "http://localhost:8001"
      : "http://localhost:8000";

    setRunning(true);
    setTrace([]);
    setFinalAnswer("");
    setAnswerExpanded(false);
    setProducts([]);
    setDecomposed(null);
    setBlocked(null);
    setLangsmithUrl(null);

    try {
      const res = await fetch(`${apiBase}/search`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: searchQuery }),
        signal: abortRef.current.signal,
      });

      const reader = res.body!.getReader();
      const dec = new TextDecoder();
      let buf = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buf += dec.decode(value, { stream: true });
        const lines = buf.split("\n\n");
        buf = lines.pop() ?? "";

        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          const raw = line.slice(6);
          try {
            const ev = JSON.parse(raw);
            if (ev.type === "start") continue;
            if (ev.type === "done") {
              if (ev.langsmith_url) setLangsmithUrl(ev.langsmith_url);
              continue;
            }

            if (ev.type === "guard_blocked") {
              setBlocked({ guard: ev.guard, reason: ev.reason });
              setTrace((t) => [...t, ev as TraceEvent]);
            } else if (ev.type === "guard_info") {
              setTrace((t) => [...t, ev as TraceEvent]);
            } else if (ev.type === "final_answer") {
              setFinalAnswer(ev.content);
              setAnswerExpanded(true);
            } else if (ev.type === "tool_result") {
              if (ev.decomposed) setDecomposed(ev.decomposed);
              if (ev.top_results) setProducts(ev.top_results);
              setTrace((t) => [...t, ev as TraceEvent]);
            } else {
              setTrace((t) => [...t, ev as TraceEvent]);
            }
          } catch {
            /* skip malformed */
          }
        }
      }
    } catch (e: unknown) {
      if ((e as Error).name !== "AbortError") {
        setTrace((t) => [...t, { type: "error", message: String(e) }]);
      }
    } finally {
      setRunning(false);
    }
  }

  const hasResults = products.length > 0 || finalAnswer || trace.length > 0;

  return (
    <div className="flex flex-col min-h-screen">
      {/* Header */}
      <header className="border-b border-border bg-card/60 backdrop-blur-sm sticky top-0 z-10">
        <div className="max-w-6xl mx-auto px-4 h-12 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Package className="w-4 h-4 text-primary" />
            <span className="font-heading text-[13px] font-semibold text-foreground">
              Product Search
            </span>
            <span
              className={`text-[10px] font-medium px-1.5 py-0.5 rounded-full border ml-1 ${
                guardMode
                  ? "bg-emerald-50 text-emerald-700 border-emerald-200"
                  : "bg-primary/10 text-primary border-primary/20"
              }`}
            >
              {guardMode ? "P6" : "P5"}
            </span>
          </div>

          <div className="flex items-center gap-3">
            {/* Guard mode toggle */}
            <button
              onClick={() => setGuardMode((v) => !v)}
              title={
                guardMode
                  ? "Click to disable P6 guard layer"
                  : "Click to enable P6 guard layer"
              }
              className={`flex items-center gap-1.5 text-[10px] font-medium px-2.5 py-1 rounded-full border transition-colors ${
                guardMode
                  ? "bg-emerald-600 text-white border-emerald-600 hover:bg-emerald-700"
                  : "bg-card text-muted-foreground border-border hover:border-primary/30 hover:text-foreground"
              }`}
            >
              {guardMode ? (
                <ShieldCheck className="w-3 h-3" />
              ) : (
                <Shield className="w-3 h-3" />
              )}
              {guardMode ? "Guarded · P6" : "Enable guards"}
            </button>

            <div className="flex items-center gap-1.5 text-[10px] text-muted-foreground">
              <Layers className="w-3 h-3" />
              SQL · BM25 · pgvector · MCP
            </div>
          </div>
        </div>
      </header>

      <main className="flex-1 max-w-6xl mx-auto w-full px-4 py-8 flex flex-col gap-6">
        {/* Search hero */}
        <section className="flex flex-col items-center gap-4">
          <div className="text-center">
            <h1 className="font-heading text-3xl font-semibold text-foreground">
              Find what you&apos;re looking for
            </h1>
            <p className="text-sm text-muted-foreground mt-1.5">
              {guardMode
                ? "Hybrid search guarded by P6 · injection, PII, topic, and output checks"
                : "Hybrid search ( filters, keywords, and semantics fused via RRF )"}
            </p>
          </div>

          <div className="w-full max-w-2xl">
            <div className="flex gap-2">
              <div className="relative flex-1">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                <input
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") runSearch();
                  }}
                  placeholder="e.g. white cotton dress for girls under ₹500"
                  className="w-full pl-9 pr-4 py-2.5 rounded-xl border border-border bg-card text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary/50 transition-colors"
                />
              </div>
              <button
                onClick={() => runSearch()}
                disabled={!query.trim() || running}
                className="px-4 py-2.5 rounded-xl bg-primary text-primary-foreground text-sm font-medium hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed transition-opacity flex items-center gap-2 shrink-0"
              >
                {running ? (
                  <>
                    <span className="btn-spinner" /> Searching
                  </>
                ) : (
                  <>
                    <Search className="w-3.5 h-3.5" /> Search
                  </>
                )}
              </button>
            </div>

            {/* Example chips */}
            {!hasResults && (
              <div className="flex flex-wrap gap-1.5 mt-3 justify-center">
                {EXAMPLE_QUERIES.map((q) => (
                  <button
                    key={q}
                    onClick={() => {
                      setQuery(q);
                      runSearch(q);
                    }}
                    className="text-[11px] px-2.5 py-1 rounded-full border border-border bg-card text-muted-foreground hover:text-foreground hover:border-primary/30 transition-colors cursor-pointer"
                  >
                    {q}
                  </button>
                ))}
              </div>
            )}
          </div>
        </section>

        {/* Results area */}
        {hasResults && (
          <div className="grid grid-cols-1 lg:grid-cols-[380px_1fr] gap-5">
            {/* Left: Pipeline trace */}
            <div className="flex flex-col gap-3">
              <div className="flex items-center justify-between">
                <h2 className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground flex items-center gap-1.5">
                  <Cpu className="w-3 h-3" /> Pipeline trace
                </h2>
                {langsmithUrl && (
                  <a
                    href={langsmithUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center gap-1 text-[10px] font-medium text-violet-600 hover:text-violet-700 transition-colors"
                  >
                    <ExternalLink className="w-3 h-3" />
                    View in LangSmith
                  </a>
                )}
              </div>

              {/* Decomposition card */}
              {decomposed && (
                <div className="rounded-xl border border-border bg-card p-3.5 flex flex-col gap-2 trace-entry">
                  <div className="flex items-center gap-1.5 text-[11px] font-semibold text-foreground">
                    <Zap className="w-3 h-3 text-primary" /> Query decomposed
                  </div>
                  <div className="text-[11px] text-muted-foreground">
                    <span className="font-medium text-foreground">
                      Semantic:
                    </span>{" "}
                    {decomposed.semantic_query}
                  </div>
                  {Object.keys(decomposed.filters).length > 0 && (
                    <div className="flex flex-wrap gap-1">
                      {Object.entries(decomposed.filters).map(([k, v]) => (
                        <FilterBadge key={k} label={k} value={v} />
                      ))}
                    </div>
                  )}
                </div>
              )}

              {/* Trace events */}
              {trace.map((ev, i) => {
                const callDone =
                  ev.type === "tool_call"
                    ? trace
                        .slice(i + 1)
                        .some(
                          (e) =>
                            e.type === "tool_result" &&
                            (e as { tool: string }).tool === ev.tool,
                        )
                    : false;

                return (
                  <div
                    key={i}
                    className={`rounded-xl border p-3 trace-entry ${
                      ev.type === "guard_blocked"
                        ? "border-rose-200 bg-rose-50"
                        : ev.type === "guard_info"
                          ? "border-amber-200 bg-amber-50"
                          : "border-border bg-card"
                    }`}
                  >
                    {ev.type === "tool_call" && (
                      <div className="flex items-center gap-1.5 text-[11px]">
                        {callDone ? (
                          <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600 shrink-0" />
                        ) : (
                          <span className="wait-spinner" />
                        )}
                        <span className="font-medium text-foreground">
                          {ev.tool}
                        </span>
                        <span className="text-muted-foreground">
                          {callDone ? "completed" : "running…"}
                        </span>
                      </div>
                    )}
                    {ev.type === "tool_result" && (
                      <div className="flex items-start gap-1.5 text-[11px]">
                        <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600 mt-0.5 shrink-0" />
                        <div>
                          <span className="font-medium text-foreground">
                            {ev.tool}
                          </span>
                          <span className="text-muted-foreground">
                            {" "}
                            returned{" "}
                          </span>
                          <span className="font-medium text-foreground">
                            {ev.result_count ?? 0} products
                          </span>
                          {ev.result_count !== undefined &&
                            ev.result_count > 0 && (
                              <span className="text-muted-foreground">
                                {" "}
                                after RRF merge
                              </span>
                            )}
                        </div>
                      </div>
                    )}
                    {ev.type === "guard_info" && (
                      <div className="flex items-start gap-1.5 text-[11px]">
                        <Shield className="w-3.5 h-3.5 text-amber-600 mt-0.5 shrink-0" />
                        <div>
                          <span className="font-medium text-amber-800">
                            {guardLabel(ev.guard)}
                          </span>
                          <span className="text-amber-600">
                            {" "}
                            · {ev.action === "rewrite" ? "scrubbed" : ev.action}
                          </span>
                          <p className="text-amber-500 mt-0.5 leading-snug">
                            {ev.reason}
                          </p>
                        </div>
                      </div>
                    )}
                    {ev.type === "guard_blocked" && (
                      <div className="flex items-start gap-1.5 text-[11px]">
                        <ShieldAlert className="w-3.5 h-3.5 text-rose-600 mt-0.5 shrink-0" />
                        <div>
                          <span className="font-medium text-rose-800">
                            {guardLabel(ev.guard)} blocked
                          </span>
                          <p className="text-rose-600 mt-0.5 leading-snug">
                            {ev.reason}
                          </p>
                        </div>
                      </div>
                    )}
                    {ev.type === "error" && (
                      <p className="text-[11px] text-destructive">
                        {ev.message}
                      </p>
                    )}
                  </div>
                );
              })}

              {running && trace.length === 0 && (
                <div className="rounded-xl border border-border bg-card p-3 flex items-center gap-2 text-[11px] text-muted-foreground">
                  <span className="wait-spinner" /> Running pipeline…
                </div>
              )}
            </div>

            {/* Right: Product cards */}
            <div className="flex flex-col gap-3">
              <h2 className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground flex items-center gap-1.5 flex-wrap">
                <Database className="w-3 h-3" /> Top results
                {products.length > 0 && (
                  <span className="ml-1 font-mono font-normal normal-case">
                    ({products.length} shown)
                  </span>
                )}
                {products.length > 0 &&
                  decomposed &&
                  Object.keys(decomposed.filters).length > 0 &&
                  (() => {
                    const exactCount = products.filter(
                      (p) =>
                        computeMismatches(p, decomposed.filters).size === 0,
                    ).length;
                    return exactCount > 0 ? (
                      <span className="ml-auto text-[9px] font-medium text-violet-600 normal-case flex items-center gap-1">
                        <span className="w-1.5 h-1.5 rounded-full bg-violet-500" />
                        {exactCount} exact · rest are similar
                      </span>
                    ) : (
                      <span className="ml-auto text-[9px] font-medium text-muted-foreground normal-case">
                        no exact matches · showing similar
                      </span>
                    );
                  })()}
              </h2>

              {blocked ? (
                <div className="flex flex-col items-center justify-center h-48 rounded-xl border border-rose-200 bg-rose-50 gap-3 px-6 text-center trace-entry">
                  <ShieldAlert className="w-7 h-7 text-rose-400" />
                  <div>
                    <p className="text-[13px] font-semibold text-rose-700">
                      Query blocked
                    </p>
                    <p className="text-[11px] text-rose-500 mt-0.5">
                      {blocked.reason}
                    </p>
                    <p className="text-[10px] text-rose-400 mt-1">
                      Guard: {guardLabel(blocked.guard)}
                    </p>
                  </div>
                </div>
              ) : products.length > 0 ? (
                <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-3">
                  {products.map((p) => (
                    <ProductCard
                      key={p.id}
                      product={p}
                      filters={decomposed?.filters ?? {}}
                    />
                  ))}
                </div>
              ) : running ? (
                <div className="flex items-center justify-center h-40 rounded-xl border border-border bg-card text-[12px] text-muted-foreground gap-2">
                  <span className="wait-spinner" /> Retrieving products…
                </div>
              ) : (
                <div className="flex items-center justify-center h-40 rounded-xl border border-dashed border-border text-[12px] text-muted-foreground">
                  No products found - try broadening your search
                </div>
              )}
            </div>
          </div>
        )}

        {/* Full-width AI recommendation  -  below the grid */}
        {finalAnswer && (
          <div className="rounded-xl border border-primary/20 bg-card p-4 trace-entry">
            <button
              onClick={() => setAnswerExpanded((v) => !v)}
              className="flex items-center gap-2 text-[12px] font-semibold text-foreground w-full text-left"
            >
              <Sparkles className="w-3.5 h-3.5 text-primary" />
              AI recommendation
              {answerExpanded ? (
                <ChevronDown className="w-3.5 h-3.5 text-muted-foreground ml-auto" />
              ) : (
                <ChevronRight className="w-3.5 h-3.5 text-muted-foreground ml-auto" />
              )}
            </button>
            {answerExpanded && (
              <div className="mt-3 md-prose">
                <ReactMarkdown>{finalAnswer}</ReactMarkdown>
              </div>
            )}
          </div>
        )}
      </main>
    </div>
  );
}
