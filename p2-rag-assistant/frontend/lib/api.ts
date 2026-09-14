const API_BASE = "/api";

export type Citation = {
  source: string;
  page: number | null;
  sheet: string | null;
  row_range: string | null;
  snippet: string;
  score: number;
};

export type LLMParams = {
  temperature: number;
  max_tokens: number;
  top_p: number;
  top_k: number;
  frequency_penalty: number;
  enable_thinking: boolean;
};

export type Settings = {
  model: string;
  prompt_version: string;
  top_k_chunks: number;
  llm_params: LLMParams;
};

export type Message = {
  id: string;
  role: "user" | "assistant";
  content: string;
  citations?: Citation[];
  model_used?: string;
  prompt_version?: string;
};

export const DEFAULT_SETTINGS: Settings = {
  model: "nvidia/nemotron-3-super-120b-a12b",
  prompt_version: "v1",
  top_k_chunks: 4,
  llm_params: {
    temperature: 0.2,
    max_tokens: 4096,
    top_p: 0.9,
    top_k: 40,
    frequency_penalty: 0.3,
    enable_thinking: false,
  },
};

export async function ingestFile(file: File) {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${API_BASE}/ingest`, { method: "POST", body: form });
  if (!res.ok) throw new Error(await res.text());
  return res.json() as Promise<{ filename: string; chunks_stored: number }>;
}

export async function queryDocs(settings: Settings, question: string) {
  const res = await fetch(`${API_BASE}/query`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      question,
      model: settings.model,
      prompt_version: settings.prompt_version,
      top_k_chunks: settings.top_k_chunks,
      llm_params: settings.llm_params,
    }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json() as Promise<{
    answer: string;
    citations: Citation[];
    model_used: string;
    prompt_version: string;
  }>;
}
