// Pure reducer: folds audit events into screen state. Every panel renders only this state.
// The UI computes nothing itself except the running totals of llm_call events (section 16).
import type { Agent, AuditEvent, BaselineStats, EquityPoint, Stats, VerdictEvent } from "./events";

export type AgentStatus = "idle" | "active" | "done" | "error";
export const agentOrder: Agent[] = ["planner", "researcher", "mathematician", "naysayer", "reporter"];

export interface UiState {
  phase: "idle" | "running" | "done";
  idea: string;
  startedAt: string | null;
  traceId: string | null;
  whatTested: string | null;
  planHash: string | null;
  agents: Record<Agent, AgentStatus>;
  lastAgent: Agent | null;
  links: { from: Agent; to: Agent; key: number } | null;
  equityTrain: EquityPoint[];
  equityValidation: EquityPoint[];
  equityRun: string | null;
  stats: { train: Stats; validation: Stats; baseline: BaselineStats } | null;
  followups: { id: string; reason: string }[];
  followupsRun: number;
  checks: { check: string; passed: boolean; value: unknown; note: string }[];
  recoveries: { failed: string; action: string; injected: boolean }[];
  verdict: VerdictEvent["payload"] | null;
  report: { path: string; traceId: string | null } | null;
  meters: { llmCalls: number; budget: number; promptTokens: number; completionTokens: number; costUsd: number };
  lastSeq: number;
  lastTs: string | null;
  errors: string[];
}

export const initialState: UiState = {
  phase: "idle",
  idea: "",
  startedAt: null,
  traceId: null,
  whatTested: null,
  planHash: null,
  agents: { planner: "idle", researcher: "idle", mathematician: "idle", naysayer: "idle", reporter: "idle", triage: "idle" },
  lastAgent: null,
  links: null,
  equityTrain: [],
  equityValidation: [],
  equityRun: null,
  stats: null,
  followups: [],
  followupsRun: 0,
  checks: [],
  recoveries: [],
  verdict: null,
  report: null,
  meters: { llmCalls: 0, budget: 8, promptTokens: 0, completionTokens: 0, costUsd: 0 },
  lastSeq: 0,
  lastTs: null,
  errors: [],
};

let linkKey = 0;
const link = (from: Agent, to: Agent) => ({ from, to, key: ++linkKey });

function summaryField(summary: unknown, field: string): string | null {
  if (summary && typeof summary === "object" && field in summary) {
    const v = (summary as Record<string, unknown>)[field];
    return typeof v === "string" ? v : null;
  }
  return null;
}

export function reduce(prev: UiState, e: AuditEvent): UiState {
  const s: UiState = { ...prev, lastSeq: e.seq, lastTs: e.ts };
  switch (e.type) {
    case "audit_started":
      return { ...s, phase: "running", idea: e.payload.idea, startedAt: e.ts, traceId: e.payload.trace_id,
        meters: { ...s.meters, budget: e.payload.llm_budget } };
    case "agent_started":
      return { ...s, phase: s.phase === "idle" ? "running" : s.phase,
        agents: { ...s.agents, [e.agent]: "active" },
        links: s.lastAgent && s.lastAgent !== e.agent ? link(s.lastAgent, e.agent) : s.links,
        lastAgent: e.agent };
    case "agent_finished":
      return { ...s, agents: { ...s.agents, [e.agent]: e.payload.status === "error" ? "error" : "done" },
        whatTested: summaryField(e.payload.summary, "what_tested") ?? s.whatTested,
        planHash: summaryField(e.payload.summary, "plan_hash") ?? s.planHash };
    case "llm_call": {
      const m = s.meters;
      return { ...s, meters: { ...m, llmCalls: m.llmCalls + 1, promptTokens: m.promptTokens + e.payload.prompt_tokens,
        completionTokens: m.completionTokens + e.payload.completion_tokens, costUsd: m.costUsd + e.payload.cost_usd } };
    }
    case "backtest_result": {
      const isFollowup = /^F\d/.test(e.payload.run);
      const next = { ...s, followupsRun: s.followupsRun + (isFollowup ? 1 : 0) };
      if (e.payload.run !== "base") return next;
      return { ...next, equityTrain: e.payload.equity_train, equityValidation: e.payload.equity_validation,
        equityRun: e.payload.run, stats: { train: e.payload.train, validation: e.payload.validation, baseline: e.payload.baseline } };
    }
    case "check_result":
      return { ...s, checks: [...s.checks, e.payload] };
    case "followup_requested":
      return { ...s, followups: [...s.followups, { id: e.payload.followup, reason: e.payload.reason }],
        links: link("naysayer", "mathematician") };
    case "recovered":
      return { ...s, recoveries: [...s.recoveries, e.payload] };
    case "verdict": {
      // Tolerate a payload with missing parts so one odd line never blanks the screen.
      const p = e.payload ?? ({} as VerdictEvent["payload"]);
      const headline = p.headline && typeof p.headline === "object" ? p.headline : {};
      const downgrades = Array.isArray(p.downgrades) ? p.downgrades : [];
      return { ...s, phase: "done", verdict: { ...p, verdict: p.verdict, reason: typeof p.reason === "string" ? p.reason : "", headline, downgrades } };
    }
    case "report_ready":
      return { ...s, report: { path: e.payload.path, traceId: e.payload.trace_id }, agents: { ...s.agents, reporter: "done" } };
    case "error":
      return { ...s, phase: "done", errors: [...s.errors, `${e.payload.step}: ${e.payload.message}`],
        agents: e.agent ? { ...s.agents, [e.agent]: "error" } : s.agents };
    default:
      return s;
  }
}
