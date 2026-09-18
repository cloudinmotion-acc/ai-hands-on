"use client"

import { useRef, useState, DragEvent } from "react"
import { ingestFile } from "@/lib/api"
import { Check, X, Upload, Plus, Minus } from "lucide-react"

type UploadedFile = { name: string; chunks: number }

type Props = {
  compact?: boolean
  uploadedFiles: UploadedFile[]
  onFilesChange: (files: UploadedFile[]) => void
}

type QueueItem = {
  name: string
  status: "pending" | "uploading" | "done" | "error" | "skipped"
  chunks?: number
  error?: string
}

const ACCEPT = ".pdf,.xlsx,.xls,.txt"
const ALLOWED = [".pdf", ".xlsx", ".xls", ".txt"]

function extOf(name: string) {
  const i = name.lastIndexOf(".")
  return i === -1 ? "" : name.slice(i).toLowerCase()
}

export function FileUpload({ compact = false, uploadedFiles, onFilesChange }: Props) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [dragging, setDragging] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [queue, setQueue] = useState<QueueItem[]>([])

  async function uploadAll(files: File[]) {
    if (!files.length || uploading) return

    // Reject unsupported types up front — the backend would 400 anyway, and
    // catching it here keeps a stray file from interrupting the batch.
    const items: QueueItem[] = files.map((f) =>
      ALLOWED.includes(extOf(f.name))
        ? { name: f.name, status: "pending" }
        : { name: f.name, status: "error", error: "Unsupported file type" }
    )
    setQueue(items)
    setUploading(true)

    // Accumulate locally: onFilesChange is called once per file, so reading
    // `uploadedFiles` from the closure would go stale after the first append.
    const accepted = [...uploadedFiles]

    for (let i = 0; i < files.length; i++) {
      if (items[i].status === "error") continue

      // If the DB already has this file, skip the embed round-trip entirely.
      // Re-embedding the same file produces identical rows (content-addressed IDs),
      // so there is no benefit — just wasted NVIDIA token spend.
      const alreadyIndexed = accepted.find((f) => f.name === files[i].name)
      if (alreadyIndexed) {
        setQueue((q) =>
          q.map((it, j) =>
            j === i ? { ...it, status: "skipped", chunks: alreadyIndexed.chunks } : it
          )
        )
        continue
      }

      setQueue((q) => q.map((it, j) => (j === i ? { ...it, status: "uploading" } : it)))

      try {
        const data = await ingestFile(files[i])
        const chunks = data.chunks_stored ?? 0
        accepted.push({ name: files[i].name, chunks })
        onFilesChange([...accepted])
        setQueue((q) =>
          q.map((it, j) => (j === i ? { ...it, status: "done", chunks } : it))
        )
      } catch (e: unknown) {
        // One bad file must not abort the rest of the batch.
        let msg = e instanceof Error ? e.message : "Upload failed"
        try {
          const p = JSON.parse(msg)
          if (p.detail) msg = p.detail
        } catch {}
        setQueue((q) => q.map((it, j) => (j === i ? { ...it, status: "error", error: msg } : it)))
      }
    }

    setUploading(false)
  }

  function onDrop(e: DragEvent<HTMLDivElement>) {
    e.preventDefault()
    setDragging(false)
    uploadAll(Array.from(e.dataTransfer.files))
  }

  function onInputChange(e: React.ChangeEvent<HTMLInputElement>) {
    uploadAll(Array.from(e.target.files ?? []))
    e.target.value = ""
  }

  const failed = queue.filter((q) => q.status === "error")
  const doneCount = queue.filter((q) => q.status === "done").length
  const activeIndex = queue.findIndex((q) => q.status === "uploading")

  // Unsupported types and already-indexed files are not part of the "X of Y"
  // progress — counting them would make the denominator disagree with position.
  const isSkipped = (it: QueueItem) =>
    it.status === "skipped" || (it.status === "error" && it.error === "Unsupported file type")
  const uploadable = queue.filter((it) => !isSkipped(it))
  const currentPos =
    activeIndex < 0 ? 0 : queue.slice(0, activeIndex + 1).filter((it) => !isSkipped(it)).length

  const fileInput = (
    <input
      ref={inputRef}
      type="file"
      multiple
      accept={ACCEPT}
      className="hidden"
      onChange={onInputChange}
    />
  )

  // ── Compact: shown under the chat thread ──
  if (compact) {
    return (
      <div className="flex items-center gap-3 flex-wrap">
        <button
          onClick={() => inputRef.current?.click()}
          disabled={uploading}
          className="inline-flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors disabled:opacity-50"
        >
          {uploading ? (
            <span className="w-3 h-3 border border-current border-t-transparent rounded-full animate-spin" />
          ) : (
            <Plus className="w-3 h-3" />
          )}
          {uploading ? `Uploading ${currentPos} of ${uploadable.length}…` : "Add files"}
        </button>

        {uploading && activeIndex >= 0 && (
          <span className="text-xs text-muted-foreground truncate max-w-[220px]">
            {queue[activeIndex].name}
          </span>
        )}

        {!uploading && failed.length > 0 && (
          <span className="text-xs text-destructive">
            {failed.length} failed · {failed[0].error}
          </span>
        )}

        {fileInput}
      </div>
    )
  }

  // ── Full: empty-state dropzone ──
  return (
    <div className="w-full max-w-sm">
      <div
        onDragOver={(e) => {
          e.preventDefault()
          setDragging(true)
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        onClick={() => !uploading && inputRef.current?.click()}
        className={[
          "rounded-xl border-2 border-dashed px-8 py-10",
          "flex flex-col items-center gap-3 cursor-pointer select-none",
          "transition-all duration-150",
          dragging
            ? "border-primary bg-primary/5 scale-[1.015]"
            : "border-border hover:border-primary/50 hover:bg-muted/60",
          uploading ? "pointer-events-none" : "",
        ].join(" ")}
      >
        {uploading ? (
          <>
            <div className="w-8 h-8 border-2 border-primary/30 border-t-primary rounded-full animate-spin" />
            <div className="text-center">
              <p className="text-sm font-medium text-foreground">
                Uploading {currentPos} of {uploadable.length}
              </p>
              <p className="text-xs text-muted-foreground mt-0.5 truncate max-w-[240px]">
                {activeIndex >= 0 ? queue[activeIndex].name : "Embedding…"}
              </p>
            </div>
          </>
        ) : (
          <>
            <Upload className="w-9 h-9 text-primary/50" strokeWidth={1.5} />
            <div className="text-center">
              <p className="text-sm font-medium text-foreground">
                {dragging ? "Drop to upload" : "Drop files here"}
              </p>
              <p className="text-xs text-muted-foreground mt-0.5">
                or click to browse · PDF, Excel or TXT
              </p>
            </div>
          </>
        )}
      </div>

      {/* Per-file results — kept visible after the batch so failures are readable */}
      {queue.length > 0 && (
        <ul className="mt-3 space-y-1.5">
          {queue.map((item, i) => (
            <li key={`${item.name}-${i}`} className="flex items-start gap-2 text-xs">
              <span className="mt-0.5 shrink-0">
                {item.status === "done"    && <Check  className="w-3 h-3 text-primary" />}
                {item.status === "skipped" && <Minus  className="w-3 h-3 text-muted-foreground" />}
                {item.status === "error"   && <X      className="w-3 h-3 text-destructive" />}
                {item.status === "uploading" && (
                  <span className="block w-3 h-3 border border-muted-foreground border-t-transparent rounded-full animate-spin" />
                )}
                {item.status === "pending" && (
                  <span className="block w-3 h-3 rounded-full border border-border" />
                )}
              </span>

              <span className="flex-1 min-w-0">
                <span
                  className={[
                    "block truncate",
                    item.status === "error"   ? "text-destructive"    : "",
                    item.status === "skipped" ? "text-muted-foreground" : "",
                    item.status === "pending" ? "text-muted-foreground" : "text-foreground",
                  ].join(" ")}
                >
                  {item.name}
                </span>
                {item.status === "done" && (
                  <span className="text-muted-foreground">{item.chunks} chunks</span>
                )}
                {item.status === "skipped" && (
                  <span className="text-muted-foreground">Already indexed · {item.chunks} chunks</span>
                )}
                {item.status === "error" && (
                  <span className="text-destructive/80 block leading-relaxed">{item.error}</span>
                )}
              </span>
            </li>
          ))}
        </ul>
      )}

      {!uploading && queue.length > 1 && (
        <p className="mt-2 text-xs text-muted-foreground">
          {doneCount} of {queue.length} ingested
          {failed.length > 0 && ` · ${failed.length} failed`}
        </p>
      )}

      {fileInput}
    </div>
  )
}
