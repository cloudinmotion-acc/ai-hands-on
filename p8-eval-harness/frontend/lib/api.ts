import type { EvalResults, EvalEvent } from "./types";

export async function fetchResults(): Promise<EvalResults | null> {
  const r = await fetch("/api/results", { cache: "no-store" });
  if (r.status === 404) return null;
  if (!r.ok) throw new Error(`Failed to load results: ${r.status}`);
  return r.json();
}

export async function streamEval(
  opts: { quick?: boolean; skipPropagation?: boolean },
  onEvent: (event: EvalEvent) => void,
  onDone: () => void,
  onError: (msg: string) => void,
): Promise<void> {
  const r = await fetch("/api/eval/run", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ quick: opts.quick ?? false, skip_propagation: opts.skipPropagation ?? false }),
  });

  if (!r.ok) {
    const err = await r.json().catch(() => ({ detail: `HTTP ${r.status}` }));
    onError(err.detail || `Eval failed: ${r.status}`);
    return;
  }

  const reader = r.body?.getReader();
  if (!reader) { onError("No response body"); return; }

  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() ?? "";

    for (const line of lines) {
      if (!line.startsWith("data: ")) continue;
      try {
        const event = JSON.parse(line.slice(6)) as EvalEvent;
        onEvent(event);
        if (event.type === "done") { onDone(); return; }
      } catch { /* ignore malformed */ }
    }
  }

  onDone();
}
