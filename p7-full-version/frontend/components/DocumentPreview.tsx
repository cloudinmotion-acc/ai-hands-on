"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Download, Plus } from "lucide-react";
import { downloadUrl } from "@/lib/api";

interface Props {
  docText: string;
  sessionId: string;
  onNewSession: () => void;
}

export function DocumentPreview({ docText, sessionId, onNewSession }: Props) {
  return (
    <div className="flex flex-col gap-4 trace-entry">
      {/* Action bar */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-[14px] font-semibold text-foreground">
            Design Document
          </h2>
          <p className="text-[11px] text-muted-foreground mt-0.5">
            All stages approved - ready to download
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={onNewSession}
            className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg text-[12px] font-medium border border-border bg-card text-muted-foreground hover:text-foreground hover:border-primary/30 transition-colors"
          >
            <Plus className="w-3.5 h-3.5" />
            New Design
          </button>

          <a
            href={downloadUrl(sessionId)}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-1.5 px-4 py-1.5 rounded-lg bg-primary text-primary-foreground text-[12px] font-medium hover:opacity-90 transition-opacity"
          >
            <Download className="w-3.5 h-3.5" />
            Download .docx
          </a>
        </div>
      </div>

      {/* Document content */}
      <div className="rounded-2xl border border-border bg-card overflow-hidden">
        <div className="px-6 py-5 max-h-[680px] overflow-y-auto">
          <div className="md-prose">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{docText}</ReactMarkdown>
          </div>
        </div>
      </div>
    </div>
  );
}
