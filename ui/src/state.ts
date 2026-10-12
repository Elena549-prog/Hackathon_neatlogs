// Pure reducer: folds audit events into screen state. Every panel renders only this state.
// The UI computes nothing itself except the running totals of llm_call events (section 16).
import type { Agent, AuditEvent, BacktestResultEvent, BaselineStats, EquityPoint, Stats, VerdictEvent } from "./events";
import { int, usd } from "./fmt";

export type AgentStatus = "idle" | "active" | "done" | "error";
export const agentOrder: Agent[] = ["planner", "researcher", "mathematician", "naysayer", "reporter"];
export const AGENT_LABEL: Record<Agent, string> = {
  planner: "Planner", researcher: "Researcher", mathematician: "Mathematician", naysayer: "Naysayer", reporter: "Reporter", triage: "Triage",
};

/** One line of the activity feed under the agent graph (spec 16, item 3). */
export interface FeedLine {
  seq: number;
  ts: string;
  agent: Agent | null;
  text: string;
  tone: "info" | "ok" | "bad" | "injected";
}
const FEED_MAX = 80;

/** One follow-up card: the Naysayer's request, then the Mathematician's result merged in by id. */
export interface Followup {
  id: string;
  reason: string;
  title?: string;
  result?: string;
  downgrade?: boolean;
  cause?: string | null;
  skipped?: boolean;
}

export interface UiState {
  phase: "idle" | "running" | "done";
  kind: "audit" | "trade";
  idea: string;
  provider: string | null;
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
  stats: { train: Stats; validation: Stats | null; baseline: BaselineStats } | null;
  followups: Followup[];
  followupsRun: number;
  checks: { check: string; passed: boolean; value: unknown; note: string }[];
  recoveries: { failed: string; action: string; injected: boolean }[];
  feed: FeedLine[];
  verdict: VerdictEvent["payload"] | null;
  report: { path: string; traceId: string | null } | null;
  meters: { llmCalls: number; budget: number; promptTokens: number; completionTokens: number; costUsd: number };
  lastSeq: number;
  lastTs: string | null;
  errors: string[];
}

export const initialState: UiState = {
  phase: "idle",
  kind: "audit",
  idea: "",
  provider: null,
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
  feed: [],
  verdict: null,
  report: null,
  meters: { llmCalls: 0, budget: 8, promptTokens: 0, completionTokens: 0, costUsd: 0 },
  lastSeq: 0,
  lastTs: null,
  errors: [],
};

let linkKey = 0;
const link = (from: Agent, to: Agent) => ({ from, to, key: ++linkKey });

/** Copy only the M2 result fields that are present and well typed; M1 event files have none of them. */
function followupResult(p: BacktestResultEvent["payload"]): Partial<Followup> {
  const out: Partial<Followup> = {};
  if (typeof p.title === "string") out.title = p.title;
  if (typeof p.result === "string") out.result = p.result;
  if (typeof p.downgrade === "boolean") out.downgrade = p.downgrade;
  if (typeof p.cause === "string" || p.cause === null) out.cause = p.cause;
  if (p.skipped === true) out.skipped = true;
  return out;
}

/** The verdict's applied downgrade for this follow-up, matched by cause; null if none was applied. */
export function appliedDowngrade(f: Followup, verdict: UiState["verdict"]): VerdictEvent["payload"]["downgrades"][number] | null {
  if (!f.downgrade || !f.cause || !verdict) return null;
  return verdict.downgrades.find((d) => d.cause === f.cause) ?? null;
}

function summaryField(summary: unknown, field: string): string | null {
  if (summary && typeof summary === "object" && field in summary) {
    const v = (summary as Record<string, unknown>)[field];
    return typeof v === "string" ? v : null;
  }
  return null;
}

const secs = (ms: number) => `${(ms / 1000).toFixed(1)}s`;

function argsText(args: unknown): string {
  if (args && typeof args === "object") return Object.entries(args as Record<string, unknown>).map(([k, v]) => `${k}=${String(v)}`).join(", ");
  return args == null ? "" : String(args);
}

/** The feed line an event adds, or null for events other panels already show (checks, results, verdict). */
function feedLine(e: AuditEvent): Pick<FeedLine, "text" | "tone"> | null {
  switch (e.type) {
    case "agent_started":
      return { text: `started ${e.payload.step}`, tone: "info" };
    case "agent_finished":
      return e.payload.status === "error"
        ? { text: `failed ${e.payload.step}`, tone: "bad" }
        : { text: `finished ${e.payload.step} in ${secs(e.payload.duration_ms)}`, tone: "ok" };
    case "llm_call":
      return { text: `${e.payload.model} · ${int(e.payload.prompt_tokens + e.payload.completion_tokens)} tokens · ${usd(e.payload.cost_usd)}`, tone: "info" };
    case "tool_called":
      return { text: `${e.payload.tool}(${argsText(e.payload.args)})`, tone: "info" };
    case "tool_result":
      return { text: `${e.payload.tool} ${e.payload.ok ? "ok" : "failed"} in ${secs(e.payload.duration_ms)} · ${e.payload.summary}`, tone: e.payload.ok ? "ok" : "bad" };
    case "data_progress":
      return { text: `data ${e.payload.percent}% · ${e.payload.what}`, tone: "info" };
    case "followup_requested":
      return { text: `asks the Mathematician for ${e.payload.followup}`, tone: "info" };
    case "recovered":
      return { text: `recovered (${e.payload.injected ? "INJECTED" : "REAL"}): ${e.payload.failed} → ${e.payload.action}`, tone: e.payload.injected ? "injected" : "bad" };
    case "error":
      return { text: `${e.payload.step}: ${e.payload.message}`, tone: "bad" };
    default:
      return null;
  }
}

export function reduce(prev: UiState, e: AuditEvent): UiState {
  const s = apply(prev, e);
  const line = feedLine(e);
  return line ? { ...s, feed: [...s.feed, { seq: e.seq, ts: e.ts, agent: e.agent, ...line }].slice(-FEED_MAX) } : s;
}

function apply(prev: UiState, e: AuditEvent): UiState {
  const s: UiState = { ...prev, lastSeq: e.seq, lastTs: e.ts };
  switch (e.type) {
    case "audit_started":
      return { ...s, phase: "running", kind: e.payload.kind === "trade" ? "trade" : "audit", idea: e.payload.idea,
        provider: e.payload.provider ?? null, startedAt: e.ts, traceId: e.payload.trace_id,
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
      const run = e.payload.run;
      if (/^F\d/.test(run)) {
        const got = followupResult(e.payload);
        const known = s.followups.some((f) => f.id === run);
        return { ...s, followupsRun: s.followupsRun + 1,
          followups: known ? s.followups.map((f) => (f.id === run ? { ...f, ...got } : f)) : [...s.followups, { id: run, reason: "", ...got }] };
      }
      if (run !== "base") return s;
      return { ...s, equityTrain: e.payload.equity_train, equityValidation: e.payload.equity_validation,
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
