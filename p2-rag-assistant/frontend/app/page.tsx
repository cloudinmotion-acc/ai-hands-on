"use client";

import { useState, useRef, useEffect } from "react";
import { queryDocs, DEFAULT_SETTINGS, Message, Settings } from "@/lib/api";
import { SettingsPanel } from "@/components/settings-panel";
import { FileUpload } from "@/components/file-upload";
import { ChatMessages } from "@/components/chat-messages";
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";
import { Settings2, X, GaugeCircle, Trash2 } from "lucide-react";
import Link from "next/link";

type UploadedFile = { name: string; chunks: number };

export default function Page() {
  const [settings, setSettings] = useState<Settings>(DEFAULT_SETTINGS);
  const [messages, setMessages] = useState<Message[]>([]);
  const [question, setQuestion] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [uploadedFiles, setUploadedFiles] = useState<UploadedFile[]>([]);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const [clearing, setClearing] = useState<"idle" | "confirm" | "working">("idle");
  const clearTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  async function handleClear() {
    if (clearing === "idle") {
      // First click — arm the button. Auto-disarm after 3 s if not confirmed.
      setClearing("confirm");
      clearTimerRef.current = setTimeout(() => setClearing("idle"), 3000);
      return;
    }
    if (clearing === "confirm") {
      if (clearTimerRef.current) clearTimeout(clearTimerRef.current);
      setClearing("working");
      try {
        await fetch("/api/sources", { method: "DELETE" });
        // Wipe client state so chips vanish and "already indexed" skip resets.
        setUploadedFiles([]);
      } catch {}
      setClearing("idle");
    }
  }

  // Load whatever is already in pgvector so the header chips survive a refresh.
  useEffect(() => {
    fetch("/api/sources")
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {
        if (data?.sources?.length) {
          setUploadedFiles(
            data.sources.map((s: { name: string; chunks: number }) => ({
              name: s.name,
              chunks: s.chunks,
            }))
          );
        }
      })
      .catch(() => {});
  }, []);

  const hasMessages = messages.length > 0;

  async function handleAsk() {
    const q = question.trim();
    if (!q || loading) return;

    const userMsg: Message = {
      id: crypto.randomUUID(),
      role: "user",
      content: q,
    };
    setMessages((prev) => [...prev, userMsg]);
    setQuestion("");
    setError(null);
    setLoading(true);

    try {
      const res = await queryDocs(settings, q);
      const assistantMsg: Message = {
        id: crypto.randomUUID(),
        role: "assistant",
        content: res.answer,
        citations: res.citations,
        model_used: res.model_used,
        prompt_version: res.prompt_version,
      };
      setMessages((prev) => [...prev, assistantMsg]);
    } catch (e: unknown) {
      let msg = e instanceof Error ? e.message : "Request failed";
      try { const p = JSON.parse(msg); if (p.detail) msg = p.detail; } catch {}
      setError(msg);
      setMessages((prev) => prev.slice(0, -1));
    } finally {
      setLoading(false);
    }
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleAsk();
    }
  }

  const inputBar = (
    <div className="space-y-2">
      {error && <p className="text-xs text-destructive">{error}</p>}
      <div className="flex gap-3 items-end">
        <Textarea
          ref={textareaRef}
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Ask a question about your document… (Enter to send, Shift+Enter for newline)"
          className="resize-none text-sm min-h-[44px] max-h-36 flex-1 bg-card"
          rows={1}
          disabled={loading}
        />
        <Button
          onClick={handleAsk}
          disabled={loading || !question.trim()}
          className="shrink-0 h-11 px-5"
        >
          {loading ? (
            <span className="flex items-center gap-2">
              <span className="w-3.5 h-3.5 border-2 border-primary-foreground/40 border-t-primary-foreground rounded-full animate-spin" />
              Thinking
            </span>
          ) : (
            "Ask"
          )}
        </Button>
      </div>
    </div>
  );

  return (
    <div className="flex flex-col h-screen overflow-hidden bg-background">
      {/* ── Top bar ── */}
      <header className="h-14 shrink-0 border-b border-border flex items-center px-5 gap-4">
        <div className="flex items-baseline gap-2 shrink-0">
          <span className="font-heading text-base font-semibold tracking-tight text-foreground">
            Chat With Your Document
          </span>
          <span className="text-xs text-muted-foreground">· Classic RAG</span>
        </div>
    
        {/* Uploaded file chips */}
        <div className="flex-1 flex items-center gap-2 overflow-x-auto min-w-0">
          {uploadedFiles.map((f, i) => (
            <span
              key={i}
              className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-medium bg-primary/10 text-primary shrink-0"
            >
              <svg width="10" height="11" viewBox="0 0 10 11" fill="none" className="opacity-80">
                <rect x="1.5" y="1" width="7" height="9" rx="1" stroke="currentColor" strokeWidth="1"/>
                <path d="M3 4h4M3 6h4M3 8h2" stroke="currentColor" strokeWidth="0.8" strokeLinecap="round"/>
              </svg>
              <span className="truncate max-w-[120px]">{f.name}</span>
              <span className="opacity-50">·{f.chunks}ch</span>
            </span>
          ))}
        </div>

        {/* Clear knowledge base — only shown when files are indexed */}
        {uploadedFiles.length > 0 && (
          <button
            onClick={handleClear}
            disabled={clearing === "working"}
            title="Delete all embeddings from the vector database"
            className={[
              "shrink-0 inline-flex items-center gap-1.5 h-8 px-3 rounded-lg text-xs font-medium transition-colors",
              clearing === "confirm"
                ? "bg-destructive/10 text-destructive hover:bg-destructive/20"
                : "text-muted-foreground hover:text-destructive hover:bg-destructive/10",
              clearing === "working" ? "opacity-50 cursor-not-allowed" : "",
            ].join(" ")}
          >
            {clearing === "working" ? (
              <span className="w-3 h-3 border border-current border-t-transparent rounded-full animate-spin" />
            ) : (
              <Trash2 className="w-3 h-3" />
            )}
            {clearing === "confirm" ? "Confirm clear?" : clearing === "working" ? "Clearing…" : "Clear KB"}
          </button>
        )}

        {/* Quality gate */}
        <Link
          href="/eval"
          className="shrink-0 inline-flex items-center gap-1.5 h-8 px-3 rounded-lg text-xs font-medium text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
        >
          <GaugeCircle className="w-3.5 h-3.5" />
          Quality Gate
        </Link>

        {/* Settings trigger */}
        <button
          onClick={() => setSettingsOpen(true)}
          className="w-8 h-8 rounded-lg flex items-center justify-center text-muted-foreground hover:text-foreground hover:bg-muted transition-colors shrink-0"
          aria-label="Open settings"
        >
          <Settings2 className="w-4 h-4" />
        </button>
      </header>

      {/* ── Main area ── */}
      <main className="flex-1 flex flex-col min-h-0">
        {hasMessages ? (
          /* ── Chat mode: messages fill space, input pinned to bottom ── */
          <>
            <ChatMessages messages={messages} loading={loading} />

            <div className="shrink-0 px-5 py-2 border-t border-border/50">
              <FileUpload
                compact
                uploadedFiles={uploadedFiles}
                onFilesChange={setUploadedFiles}
              />
            </div>

            <div className="shrink-0 border-t border-border px-5 py-4">
              {inputBar}
            </div>
          </>
        ) : (
          /* ── Empty mode: upload + input grouped together in center ── */
          /* Scroll lives on the outer div; the inner min-h-full wrapper keeps the
             group centered when it fits and lets it scroll from the top when the
             upload results make it taller than the viewport. Putting justify-center
             on the scroller itself would strand the top of the content above it. */
          <div className="flex-1 min-h-0 overflow-y-auto">
            <div className="min-h-full flex flex-col items-center justify-center px-5 py-8">
              {/* Heading */}
              <div className="flex flex-col items-center gap-3 text-center mb-7">
                <svg width="44" height="44" viewBox="0 0 44 44" fill="none" className="text-primary/40">
                  <rect x="8" y="4" width="24" height="36" rx="3" stroke="currentColor" strokeWidth="1.5"/>
                  <path d="M14 14h16M14 20h16M14 26h10" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
                  <path d="M26 4v9h6" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                </svg>
                <h1 className="font-heading text-2xl font-semibold text-foreground tracking-tight">
                  Chat With Your Document
                </h1>
                <p className="text-sm text-muted-foreground max-w-xs leading-relaxed">
                  Upload one or more documents, then ask questions to get cited answers.
                </p>
              </div>

              {/* Upload zone */}
              <FileUpload
                uploadedFiles={uploadedFiles}
                onFilesChange={setUploadedFiles}
              />

              {/* Input bar — directly below upload zone */}
              <div className="w-full max-w-sm mt-5">
                {inputBar}
              </div>
            </div>
          </div>
        )}
      </main>

      {/* ── Settings overlay ── */}
      {settingsOpen && (
        <>
          <div
            className="fixed inset-0 z-40 bg-foreground/10 backdrop-blur-[2px]"
            onClick={() => setSettingsOpen(false)}
          />
          <aside className="fixed top-0 right-0 bottom-0 z-50 w-80 bg-card border-l border-border shadow-xl flex flex-col">
            <div className="h-14 shrink-0 flex items-center justify-between px-5 border-b border-border">
              <span className="font-heading text-sm font-semibold text-foreground">
                Settings
              </span>
              <button
                onClick={() => setSettingsOpen(false)}
                className="w-7 h-7 rounded-md flex items-center justify-center text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
                aria-label="Close settings"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
            <SettingsPanel settings={settings} onChange={setSettings} />
          </aside>
        </>
      )}
    </div>
  );
}
