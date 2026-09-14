"use client"

import { useRef, useState, DragEvent } from "react"
import { ingestFile } from "@/lib/api"

type UploadedFile = { name: string; chunks: number }

type Props = {
  compact?: boolean
  uploadedFiles: UploadedFile[]
  onFilesChange: (files: UploadedFile[]) => void
}

export function FileUpload({ compact = false, uploadedFiles, onFilesChange }: Props) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [dragging, setDragging] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [uploadError, setUploadError] = useState<string | null>(null)

  async function upload(file: File) {
    setUploading(true)
    setUploadError(null)
    try {
      const data = await ingestFile(file)
      onFilesChange([...uploadedFiles, { name: file.name, chunks: data.chunks_stored ?? 0 }])
    } catch (e: unknown) {
      let msg = e instanceof Error ? e.message : "Upload failed"
      try { const p = JSON.parse(msg); if (p.detail) msg = p.detail } catch {}
      setUploadError(msg)
    } finally {
      setUploading(false)
    }
  }

  function onDrop(e: DragEvent<HTMLDivElement>) {
    e.preventDefault()
    setDragging(false)
    const file = e.dataTransfer.files[0]
    if (file) upload(file)
  }

  function onInputChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (file) upload(file)
    e.target.value = ""
  }

  if (compact) {
    return (
      <div className="flex items-center gap-3">
        <button
          onClick={() => inputRef.current?.click()}
          disabled={uploading}
          className="inline-flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors disabled:opacity-50"
        >
          {uploading ? (
            <span className="w-3 h-3 border border-current border-t-transparent rounded-full animate-spin" />
          ) : (
            <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
              <path d="M6 1.5v6M3.5 4l2.5-2.5L8.5 4M1.5 9v1a.5.5 0 00.5.5h8a.5.5 0 00.5-.5V9"
                stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          )}
          {uploading ? "Uploading…" : "Upload another file"}
        </button>
        {uploadError && <span className="text-xs text-destructive">{uploadError}</span>}
        <input ref={inputRef} type="file" accept=".pdf,.xlsx,.xls" className="hidden" onChange={onInputChange} />
      </div>
    )
  }

  return (
    <div className="w-full max-w-sm">
      <div
        onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
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
          uploading ? "pointer-events-none opacity-60" : "",
        ].join(" ")}
      >
        {uploading ? (
          <>
            <div className="w-8 h-8 border-2 border-primary/30 border-t-primary rounded-full animate-spin" />
            <p className="text-sm text-muted-foreground">Uploading & embedding…</p>
          </>
        ) : (
          <>
            <svg width="36" height="36" viewBox="0 0 36 36" fill="none" className="text-primary/50">
              <path d="M18 5v18M11 12l7-7 7 7" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
              <path d="M4 26v3a3 3 0 003 3h22a3 3 0 003-3v-3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
            </svg>
            <div className="text-center">
              <p className="text-sm font-medium text-foreground">
                {dragging ? "Drop to upload" : "Drop a file here"}
              </p>
              <p className="text-xs text-muted-foreground mt-0.5">
                or click to browse · PDF or Excel
              </p>
            </div>
          </>
        )}

        {uploadError && (
          <p className="text-xs text-destructive mt-1 text-center">{uploadError}</p>
        )}
      </div>

      <input ref={inputRef} type="file" accept=".pdf,.xlsx,.xls" className="hidden" onChange={onInputChange} />
    </div>
  )
}
