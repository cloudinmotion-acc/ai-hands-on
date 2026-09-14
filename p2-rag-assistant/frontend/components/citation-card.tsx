"use client"

import { useState } from "react"
import { Citation } from "@/lib/api"

function scoreLabel(score: number): { text: string; cls: string } {
  if (score >= 0.85) return { text: "high", cls: "text-primary bg-primary/10" }
  if (score >= 0.70) return { text: "mid", cls: "text-amber-700 bg-amber-500/10" }
  return { text: "low", cls: "text-muted-foreground bg-muted" }
}

export function CitationCard({ citation, index }: { citation: Citation; index: number }) {
  const [expanded, setExpanded] = useState(false)

  const location = citation.page != null
    ? `p. ${citation.page + 1}`
    : citation.sheet
    ? `${citation.sheet} · rows ${citation.row_range}`
    : null

  const { text, cls } = scoreLabel(citation.score)

  return (
    <div className="rounded-lg border border-border bg-card px-4 py-3 text-xs space-y-2 shadow-sm">
      <div className="flex items-start justify-between gap-2">
        <div className="flex flex-wrap items-baseline gap-x-1.5 gap-y-0.5 min-w-0">
          <span className="font-semibold text-foreground">[{index + 1}]</span>
          <span className="text-foreground truncate max-w-[180px]">{citation.source}</span>
          {location && <span className="text-muted-foreground">{location}</span>}
        </div>
        <span className={`shrink-0 px-1.5 py-0.5 rounded text-[10px] font-medium leading-none ${cls}`}>
          {text} · {(citation.score * 100).toFixed(0)}%
        </span>
      </div>

      <p
        className={`text-muted-foreground leading-relaxed cursor-pointer ${!expanded ? "line-clamp-2" : ""}`}
        onClick={() => setExpanded(e => !e)}
      >
        {citation.snippet}
      </p>

      {citation.snippet.length > 120 && (
        <button
          onClick={() => setExpanded(e => !e)}
          className="text-[10px] text-primary hover:underline underline-offset-2"
        >
          {expanded ? "show less" : "show more"}
        </button>
      )}
    </div>
  )
}
