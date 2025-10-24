export type NodeType = "generic" | "trigger" | "act" | "assert" | "hook";
export type NodeSource = "code" | "manual";
export type EvalStatus =
  | "pending"
  | "running"
  | "passed"
  | "failed"
  | "skipped"
  | "error"
  | "cancelled"
  | "timed_out"
  | "flaky";

export interface NodeCondition {
  timeout_ms?: number | null;
}

export interface Expr {
  engine: "python" | "js" | "cel";
  script: string;
}

export interface Node {
  id: string;
  flow: string;
  type: NodeType;
  source: NodeSource;
  description?: string | null;
  dep_ids: string[];
  filter?: Expr | null;
  validator?: Expr | null;
  conditions?: NodeCondition[];
  status: string;
  created_at: string | number; // ISO string or microseconds
  updated_at?: string | number | null; // ISO string or microseconds
  deleted_at?: string | number | null; // ISO string or microseconds
}

export interface Event {
  id: string;
  run_id: string;
  type: NodeType;
  flow: string;
  node_id: string;
  data: Record<string, unknown>;
  ts: number; // Microseconds since epoch
}

export interface BaseEvalItemOutput {
  node_id: string;
  dep_node_ids: string[];
  status: EvalStatus;
  message?: string | null;
  error?: string | null;
  elapsed_ns: number;
  ev_ids: string[];
  upstream_ev_ids: string[];
}

export interface BaseEvalOutput {
  status: EvalStatus;
  elapsed_ns: number;
  graph: Record<string, string[]>;
  exec_info: BaseEvalItemOutput[];
  ev_ids: string[];
}

export interface EvalOutput {
  id: string;
  flow: string;
  output: BaseEvalOutput;
  created_at: string | number; // ISO string or microseconds
}

export interface ApiConfig {
  apiKey: string;
  apiUrl: string;
}
