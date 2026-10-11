// Audit event contract, AUDITOR_SPEC.md section 16. One JSON object per line of events.jsonl.

export type Agent = "planner" | "researcher" | "mathematician" | "naysayer" | "reporter" | "triage";
export type Verdict = "kill" | "inconclusive" | "promising" | "cannot_audit";

export interface Stats {
  n: number;
  blocks: number;
  win_rate: number;
  mean: number;
  median: number;
  ci_low: number;
  ci_high: number;
  worst_trade: number;
  worst_window: number;
}
export type BaselineStats = Stats & { paired_ci_low: number };
export type EquityPoint = [string, number];

interface Base<T extends string, A extends Agent | null, P> {
  seq: number;
  ts: string;
  audit_id: string;
  type: T;
  agent: A;
  payload: P;
}

export type AuditStartedEvent = Base<"audit_started", null, { idea: string; trace_id: string | null; llm_budget: number; fault: string | null }>;
export type AgentStartedEvent = Base<"agent_started", Agent, { step: string }>;
export type AgentFinishedEvent = Base<"agent_finished", Agent, { step: string; status: "ok" | "error"; duration_ms: number; summary: unknown }>;
export type LlmCallEvent = Base<"llm_call", Agent, { model: string; prompt_tokens: number; completion_tokens: number; cost_usd: number; latency_ms: number }>;
export type ToolCalledEvent = Base<"tool_called", Agent, { tool: string; args: unknown }>;
export type ToolResultEvent = Base<"tool_result", Agent, { tool: string; ok: boolean; duration_ms: number; summary: string }>;
export type DataProgressEvent = Base<"data_progress", "researcher", { what: string; percent: number }>;
export type BacktestResultEvent = Base<"backtest_result", "mathematician", {
  run: string;
  train: Stats;
  validation: Stats;
  baseline: BaselineStats;
  equity_train: EquityPoint[];
  equity_validation: EquityPoint[];
  histogram: unknown;
}>;
export type CheckResultEvent = Base<"check_result", "naysayer", { check: string; passed: boolean; value: unknown; note: string }>;
export type FollowupRequestedEvent = Base<"followup_requested", "naysayer", { followup: string; reason: string }>;
export type RecoveredEvent = Base<"recovered", Agent | null, { failed: string; action: string; injected: boolean }>;
export type VerdictEvent = Base<"verdict", null, {
  verdict: Verdict;
  reason: string;
  headline: { n?: number; mean?: number; ci_low?: number; paired_ci_low?: number };
  downgrades: { cause?: string; [k: string]: unknown }[];
}>;
export type ReportReadyEvent = Base<"report_ready", "reporter", { path: string; trace_id: string | null; prose_included: boolean }>;
export type ErrorEvent = Base<"error", Agent | null, { step: string; message: string }>;

export type AuditEvent =
  | AuditStartedEvent
  | AgentStartedEvent
  | AgentFinishedEvent
  | LlmCallEvent
  | ToolCalledEvent
  | ToolResultEvent
  | DataProgressEvent
  | BacktestResultEvent
  | CheckResultEvent
  | FollowupRequestedEvent
  | RecoveredEvent
  | VerdictEvent
  | ReportReadyEvent
  | ErrorEvent;

export interface AuditSummary {
  audit_id: string;
  idea: string;
  started_at: string;
  finished: boolean;
}
