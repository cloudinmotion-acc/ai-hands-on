"use client";

import { useState, useEffect } from "react";

interface Props {
  initialContent: string;
  onSubmit: (content: string) => void;
  onCancel: () => void;
  isSubmitting: boolean;
}

export function EditPanel({
  initialContent,
  onSubmit,
  onCancel,
  isSubmitting,
}: Props) {
  const [text, setText] = useState(initialContent);

  useEffect(() => {
    setText(initialContent);
  }, [initialContent]);

  return (
    <div className="flex flex-col gap-3 mt-3 pt-3 border-t border-border animate-in fade-in slide-in-from-top-2 duration-200">
      <p className="text-[11px] font-medium text-muted-foreground uppercase tracking-wide">
        Edit content - changes will propagate to downstream stages
      </p>

      <textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        rows={16}
        className="w-full rounded-xl border border-border bg-muted/40 px-3 py-2.5 text-[13px] text-foreground font-mono leading-relaxed focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary/50 transition-colors resize-y"
        placeholder="Edit the content…"
        disabled={isSubmitting}
      />

      <div className="flex items-center gap-2 justify-end">
        <button
          onClick={onCancel}
          disabled={isSubmitting}
          className="px-3.5 py-1.5 rounded-lg text-[12px] font-medium border border-border bg-card text-muted-foreground hover:text-foreground hover:border-primary/30 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          Cancel
        </button>
        <button
          onClick={() => onSubmit(text.trim())}
          disabled={isSubmitting || !text.trim()}
          className="px-3.5 py-1.5 rounded-lg text-[12px] font-medium bg-primary text-primary-foreground hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed transition-opacity flex items-center gap-1.5"
        >
          {isSubmitting ? (
            <>
              <span className="btn-spinner" /> Saving…
            </>
          ) : (
            "Submit Edit"
          )}
        </button>
      </div>
    </div>
  );
}
