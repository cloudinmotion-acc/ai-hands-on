export type Stage = "scoping" | "solution" | "hld" | "lld" | "doc" | "complete";

export interface StageResult {
  content: string;
  approved: boolean;
  edited: boolean;
}

export interface SessionState {
  session_id: string;
  requirement: string;
  current_stage: Stage;
  scope: StageResult | null;
  solution: StageResult | null;
  hld: StageResult | null;
  lld: StageResult | null;
  doc_text: string | null;
  docx_path: string | null;
  awaiting_review: boolean;
}

export type SSEEvent =
  | { type: "token"; content: string }
  | { type: "node_start"; stage: string; label: string }
  | { type: "stage_complete"; stage: Stage; content: string; next_nodes: string[] }
  | { type: "checkpoint_saved"; stage: string; label: string }
  | { type: "checkpoint_restored"; stage: string; label: string }
  | { type: "awaiting_review"; stage: Stage }
  | { type: "session_complete" }
  | { type: "done" }
  | { type: "error"; message: string };

export interface TraceEntry {
  ts: number;
  event: SSEEvent;
}
