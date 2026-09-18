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

/**
 * P3-only settings. The generator half is P2's `Settings` verbatim — the eval
 * drives the real /query endpoint, so it must send exactly what the chat sends.
 * The judge half is separate because it scores the answers rather than making
 * them, and points at whichever OpenAI-compatible server hosts the judge model.
 */
export type EvalSettings = Settings & {
  judge_model: string;
  judge_base_url: string;
  /**
   * Sent as extra_body.reasoning_effort when non-empty. "none" suppresses
   * chain-of-thought on Ollama — measured 40s per judge call versus 200-800s
   * with it on. Leave blank for providers that reject the field.
   */
  judge_reasoning_effort: string;
};

export const NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1";
export const OLLAMA_BASE_URL = "http://localhost:11434/v1";

export const NVIDIA_MODELS = [
  { value: "nvidia/nemotron-3-super-120b-a12b",    label: "nemotron-3-super-120b  (flagship)" },
  { value: "meta/llama-3.2-90b-vision-instruct",   label: "llama-3.2-90b-vision  (large)" },
  { value: "meta/llama-3.2-11b-vision-instruct",   label: "llama-3.2-11b-vision  (lightweight)" },
];

export const DEFAULT_EVAL_SETTINGS: EvalSettings = {
  model: "nvidia/nemotron-3-super-120b-a12b",
  prompt_version: "v1",
  top_k_chunks: 4,
  llm_params: {
    temperature: 0.2,
    max_tokens: 1024,
    top_p: 0.7,
    top_k: 40,
    frequency_penalty: 0.0,
    enable_thinking: false,
  },
  judge_model: "openai/gpt-oss-20b",
  judge_base_url: NVIDIA_BASE_URL,
  judge_reasoning_effort: "",
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
