export type Verdict = "GO" | "NO-GO";
export type Stage = "scoping" | "solution" | "hld" | "lld";

export interface TrajectoryResult {
  pass: boolean;
  score: number;
  missing: string[];
  order_correct: boolean;
  stages_completed: string[];
  duration_s?: number;
  error?: string | null;
}

export interface CompletenessResult {
  scoping: number | null;
  solution: number | null;
  hld: number | null;
  lld: number | null;
  mean: number | null;
}

export interface PropagationResult {
  pass: boolean;
  scenario: string;
  edit_stage: string;
  check_stage: string;
  injected: string;
  search_term: string;
  found: boolean;
  evidence: string;
  error?: string | null;
}

export interface ScenarioRow {
  id: number;
  title: string;
  requirement: string;
  trajectory: TrajectoryResult;
  completeness: CompletenessResult;
  duration_s?: number;
  error?: string | null;
}

export interface EvalResults {
  run_id: string;
  verdict: Verdict;
  scenarios_total: number;
  scenarios_run: number;
  trajectory: {
    pass: boolean;
    score: number;
    passed: number;
    total: number;
    threshold: number;
  };
  completeness: {
    pass: boolean;
    mean: number;
    /** Lowest stage score — this is what the threshold is applied to.
     *  Optional: reports written before this field existed won't have it. */
    min?: number;
    min_stage?: string;
    threshold: number;
    scoping: { score: number; threshold: number };
    solution: { score: number; threshold: number };
    hld: { score: number; threshold: number };
    lld: { score: number; threshold: number };
  };
  propagation: PropagationResult & { threshold: boolean };
  scenarios: ScenarioRow[];
  duration_s: number;
}

export type EvalEvent =
  | { type: "eval_start"; scenarios_count: number; quick: boolean }
  | { type: "scenario_start"; id: number; title: string; index: number; total: number }
  | { type: "scenario_done"; id: number; title: string; trajectory: TrajectoryResult; error: string | null }
  | { type: "completeness_start"; scenarios_count: number }
  | { type: "completeness_done"; mean: number }
  | { type: "propagation_start" }
  | { type: "propagation_done"; pass: boolean }
  | { type: "scorecard_ready"; verdict: Verdict; result: EvalResults }
  | { type: "done" }
  | { type: "error"; message: string };

export interface ProgressItem {
  id: string;
  text: string;
  status: "running" | "pass" | "fail" | "info";
  ts: number;
}
