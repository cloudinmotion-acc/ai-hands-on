const BASE = "http://localhost:8000";

export async function createSession(): Promise<string> {
  const r = await fetch(`${BASE}/sessions`, { method: "POST" });
  if (!r.ok) throw new Error(`Failed to create session: ${r.status}`);
  const d = await r.json();
  return d.session_id as string;
}

export async function getState(sessionId: string): Promise<unknown> {
  const r = await fetch(`${BASE}/sessions/${sessionId}/state`);
  if (!r.ok) throw new Error(`Session not found: ${r.status}`);
  return r.json();
}

export async function startSession(
  sessionId: string,
  requirement: string
): Promise<Response> {
  const r = await fetch(`${BASE}/sessions/${sessionId}/start`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ requirement }),
  });
  if (!r.ok) {
    const err = await r.json().catch(() => ({ detail: `HTTP ${r.status}` }));
    throw new Error(err.detail || `Start failed: ${r.status}`);
  }
  return r;
}

export async function resumeSession(
  sessionId: string,
  action: "approve" | "edit",
  content?: string
): Promise<Response> {
  const r = await fetch(`${BASE}/sessions/${sessionId}/resume`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ action, content }),
  });
  if (!r.ok) {
    const err = await r.json().catch(() => ({ detail: `HTTP ${r.status}` }));
    throw new Error(err.detail || `Resume failed: ${r.status}`);
  }
  return r;
}

export async function regenerateFrom(
  sessionId: string,
  fromStage: string
): Promise<Response> {
  const r = await fetch(`${BASE}/sessions/${sessionId}/regenerate/${fromStage}`, {
    method: "POST",
  });
  if (!r.ok) {
    const err = await r.json().catch(() => ({ detail: `HTTP ${r.status}` }));
    throw new Error(err.detail || `Regenerate failed: ${r.status}`);
  }
  return r;
}

export function downloadUrl(sessionId: string): string {
  return `${BASE}/sessions/${sessionId}/download`;
}
