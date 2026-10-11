import { describe, it, expect } from "vitest";
import { initialState, reduce } from "./state";
import type { AuditEvent } from "./events";

const base = { ts: "2026-10-11T12:00:00Z", audit_id: "a" };
const ev = (seq: number, e: object) => ({ seq, ...base, ...e }) as AuditEvent;
const stats = { n: 1, blocks: 1, win_rate: 0, mean: 0, median: 0, ci_low: 0, ci_high: 0, worst_trade: 0, worst_window: 0 };
const bt = (seq: number, run: string, pts: [string, number][]) =>
  ev(seq, { type: "backtest_result", agent: "mathematician", payload: { run, train: stats, validation: stats, baseline: { ...stats, paired_ci_low: 0 }, equity_train: pts, equity_validation: pts, histogram: {} } });

describe("reduce", () => {
  it("audit_started sets idea, date, trace and phase", () => {
    const s = reduce(initialState, ev(1, { type: "audit_started", agent: null, payload: { idea: "x", trace_id: "t", llm_budget: 8, fault: null } }));
    expect(s).toMatchObject({ phase: "running", idea: "x", startedAt: base.ts, traceId: "t", meters: { budget: 8 }, lastSeq: 1 });
  });

  it("agent start/finish drive statuses and a link from the previous agent", () => {
    let s = reduce(initialState, ev(1, { type: "agent_started", agent: "planner", payload: { step: "plan" } }));
    expect(s.agents.planner).toBe("active");
    expect(s.links).toBeNull();
    s = reduce(s, ev(2, { type: "agent_finished", agent: "planner", payload: { step: "plan", status: "ok", duration_ms: 1, summary: { what_tested: "W", plan_hash: "H" } } }));
    expect(s.agents.planner).toBe("done");
    expect(s.whatTested).toBe("W");
    expect(s.planHash).toBe("H");
    s = reduce(s, ev(3, { type: "agent_started", agent: "researcher", payload: { step: "data" } }));
    expect(s.links).toMatchObject({ from: "planner", to: "researcher" });
  });

  it("an agent finishing with status error is marked error", () => {
    const s = reduce(initialState, ev(1, { type: "agent_finished", agent: "planner", payload: { step: "plan", status: "error", duration_ms: 1, summary: null } }));
    expect(s.agents.planner).toBe("error");
  });

  it("followup_requested animates naysayer -> mathematician with a fresh key each time", () => {
    let s = reduce(initialState, ev(1, { type: "followup_requested", agent: "naysayer", payload: { followup: "F2", reason: "r" } }));
    const k1 = s.links?.key;
    s = reduce(s, ev(2, { type: "followup_requested", agent: "naysayer", payload: { followup: "F4", reason: "q" } }));
    expect(s.followups).toEqual([{ id: "F2", reason: "r" }, { id: "F4", reason: "q" }]);
    expect(s.links).toMatchObject({ from: "naysayer", to: "mathematician" });
    expect(s.links?.key).not.toBe(k1);
  });

  it("llm_call accumulates meters", () => {
    const call = { type: "llm_call", agent: "planner", payload: { model: "m", prompt_tokens: 10, completion_tokens: 5, cost_usd: 0.01, latency_ms: 1 } };
    const s = reduce(reduce(initialState, ev(1, call)), ev(2, call));
    expect(s.meters).toMatchObject({ llmCalls: 2, promptTokens: 20, completionTokens: 10 });
    expect(s.meters.costUsd).toBeCloseTo(0.02);
  });

  it("only the base run feeds the equity curves and stats; follow-up runs are counted", () => {
    let s = reduce(initialState, bt(1, "base", [["2025-01-02", 0.1]]));
    s = reduce(s, bt(2, "F2", [["2025-01-02", 9]]));
    s = reduce(s, bt(3, "F4", [["2025-01-02", 9]]));
    expect(s.equityTrain).toEqual([["2025-01-02", 0.1]]);
    expect(s.equityRun).toBe("base");
    expect(s.stats?.validation.n).toBe(1);
    expect(s.followupsRun).toBe(2);
  });

  it("verdict without backtests still shows", () => {
    const s = reduce(initialState, ev(1, { type: "verdict", agent: null, payload: { verdict: "cannot_audit", reason: "refused", headline: {}, downgrades: [] } }));
    expect(s.phase).toBe("done");
    expect(s.verdict?.verdict).toBe("cannot_audit");
    expect(s.equityTrain).toEqual([]);
  });

  it("report_ready stores the report and finishes the reporter", () => {
    const s = reduce(initialState, ev(1, { type: "report_ready", agent: "reporter", payload: { path: "p", trace_id: "t", prose_included: false } }));
    expect(s.report).toEqual({ path: "p", traceId: "t" });
    expect(s.agents.reporter).toBe("done");
  });

  it("recovered and error are kept; checks are kept", () => {
    let s = reduce(initialState, ev(1, { type: "recovered", agent: "researcher", payload: { failed: "f", action: "a", injected: true } }));
    s = reduce(s, ev(2, { type: "check_result", agent: "naysayer", payload: { check: "evidence", passed: true, value: 1, note: "n" } }));
    s = reduce(s, ev(3, { type: "error", agent: null, payload: { step: "run", message: "boom" } }));
    expect(s.recoveries[0].injected).toBe(true);
    expect(s.checks).toHaveLength(1);
    expect(s.errors).toEqual(["run: boom"]);
    expect(s.phase).toBe("done");
  });

  it("does not mutate the previous state", () => {
    const before = JSON.stringify(initialState);
    reduce(initialState, ev(1, { type: "agent_started", agent: "planner", payload: { step: "plan" } }));
    expect(JSON.stringify(initialState)).toBe(before);
  });
});

describe("reduce: tolerates a verdict payload with missing parts", () => {
  it("normalises a null headline and missing downgrades", () => {
    const s = reduce(initialState, ev(1, { type: "verdict", agent: null, payload: { verdict: "kill", reason: "r", headline: null } }));
    expect(s.verdict?.headline).toEqual({});
    expect(s.verdict?.downgrades).toEqual([]);
  });
});

describe("reduce: provider of the run", () => {
  it("keeps the provider from audit_started so fake-LLM runs can be labelled", () => {
    const s = reduce(initialState, ev(1, { type: "audit_started", agent: null, payload: { idea: "x", trace_id: null, llm_budget: 8, fault: null, provider: "fake" } }));
    expect(s.provider).toBe("fake");
    const real = reduce(initialState, ev(1, { type: "audit_started", agent: null, payload: { idea: "x", trace_id: null, llm_budget: 8, fault: null } }));
    expect(real.provider).toBeNull();
  });
});
