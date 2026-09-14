"use client"

import { useEffect, useRef, useState } from "react"
import ReactMarkdown, { type Components } from "react-markdown"
import { Message } from "@/lib/api"
import { CitationCard } from "@/components/citation-card"
import { ChevronDown, ChevronUp } from "lucide-react"

const md: Components = {
  p({ children }) {
    return <p className="mb-2 last:mb-0 leading-relaxed">{children}</p>
  },
  strong({ children }) {
    return <strong className="font-semibold text-foreground">{children}</strong>
  },
  em({ children }) {
    return <em className="italic">{children}</em>
  },
  ul({ children }) {
    return <ul className="list-disc pl-4 mb-2 space-y-0.5">{children}</ul>
  },
  ol({ children }) {
    return <ol className="list-decimal pl-4 mb-2 space-y-0.5">{children}</ol>
  },
  li({ children }) {
    return <li className="leading-relaxed">{children}</li>
  },
  h1({ children }) {
    return <h2 className="font-heading font-semibold text-[15px] mb-2 mt-4 first:mt-0">{children}</h2>
  },
  h2({ children }) {
    return <h2 className="font-heading font-semibold text-sm mb-1.5 mt-3 first:mt-0">{children}</h2>
  },
  h3({ children }) {
    return <h3 className="font-semibold text-sm mb-1 mt-2.5 first:mt-0">{children}</h3>
  },
  code({ children }) {
    return <code className="bg-muted px-1.5 py-0.5 rounded text-[12px] font-mono">{children}</code>
  },
  blockquote({ children }) {
    return (
      <blockquote className="border-l-2 border-primary/40 pl-3 text-muted-foreground italic my-2">
        {children}
      </blockquote>
    )
  },
}

function CitationsList({
  citations,
  promptVersion,
}: {
  citations: NonNullable<Message["citations"]>
  promptVersion?: string
}) {
  const [open, setOpen] = useState(false)

  return (
    <div className="ml-0.5">
      <button
        onClick={() => setOpen(v => !v)}
        className="inline-flex items-center gap-1.5 text-[11px] text-muted-foreground hover:text-foreground transition-colors py-1"
      >
        {open ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
        <span>
          {citations.length} source{citations.length !== 1 ? "s" : ""}
        </span>
        {promptVersion && (
          <span className="px-1.5 py-0 rounded border border-border text-[10px] leading-4">
            {promptVersion}
          </span>
        )}
      </button>

      {open && (
        <div className="mt-2 space-y-2">
          {citations.map((c, i) => (
            <CitationCard key={i} citation={c} index={i} />
          ))}
        </div>
      )}
    </div>
  )
}

export function ChatMessages({
  messages,
  loading,
}: {
  messages: Message[]
  loading: boolean
}) {
  const containerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const el = containerRef.current
    if (el) el.scrollTop = el.scrollHeight
  }, [messages, loading])

  return (
    <div ref={containerRef} className="flex-1 overflow-y-auto">
      <div className="max-w-2xl mx-auto px-5 py-6 flex flex-col gap-7">
        {messages.map(msg => (
          <div
            key={msg.id}
            className={`flex flex-col gap-2 ${msg.role === "user" ? "items-end" : "items-start"}`}
          >
            {msg.role === "user" ? (
              <div className="max-w-[78%] rounded-2xl rounded-tr-sm bg-primary text-primary-foreground px-4 py-2.5 text-sm leading-relaxed">
                {msg.content}
              </div>
            ) : (
              <div className="w-full space-y-3">
                <div className="rounded-2xl rounded-tl-sm bg-card border border-border px-5 py-4 text-sm text-foreground shadow-sm">
                  <ReactMarkdown components={md}>{msg.content}</ReactMarkdown>
                </div>
                {msg.citations && msg.citations.length > 0 && (
                  <CitationsList
                    citations={msg.citations}
                    promptVersion={msg.prompt_version}
                  />
                )}
              </div>
            )}
          </div>
        ))}

        {loading && (
          <div className="flex items-start">
            <div className="rounded-2xl rounded-tl-sm bg-card border border-border px-5 py-4 text-sm text-muted-foreground flex items-center gap-2.5 shadow-sm">
              <span className="w-3.5 h-3.5 border-2 border-muted-foreground/30 border-t-muted-foreground rounded-full animate-spin" />
              Consulting the document…
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
