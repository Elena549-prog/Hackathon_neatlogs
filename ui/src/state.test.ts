import { describe, it, expect } from "vitest";
import { appliedDowngrade, initialState, reduce } from "./state";
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

describe("reduce: activity feed", () => {
  it("adds one terse line per agent step, LLM call, tool call, data progress and recovery", () => {
    const events = [
      ev(1, { type: "agent_started", agent: "researcher", payload: { step: "data" } }),
      ev(2, { type: "tool_called", agent: "researcher", payload: { tool: "get_prices", args: { group: "tech", tickers: 17 } } }),
      ev(3, { type: "tool_result", agent: "researcher", payload: { tool: "get_prices", ok: true, duration_ms: 1200, summary: "17 tickers with prices, 0 skipped" } }),
      ev(4, { type: "data_progress", agent: "researcher", payload: { what: "prices", percent: 33 } }),
      ev(5, { type: "recovered", agent: "researcher", payload: { failed: "dolthub timeout", action: "retried", injected: true } }),
      ev(6, { type: "llm_call", agent: "naysayer", payload: { model: "m", prompt_tokens: 1000, completion_tokens: 234, cost_usd: 0.0012, latency_ms: 1 } }),
      ev(7, { type: "check_result", agent: "naysayer", payload: { check: "evidence", passed: true, value: 1, note: "n" } }),
    ];
    const s = events.reduce(reduce, initialState);
    expect(s.feed.map((l) => l.text)).toEqual([
      "started data",
      "get_prices(group=tech, tickers=17)",
      "get_prices ok in 1.2s · 17 tickers with prices, 0 skipped",
      "data 33% · prices",
      "recovered (INJECTED): dolthub timeout → retried",
      "m · 1,234 tokens · $0.0012",
    ]);
    expect(s.feed[4]).toMatchObject({ seq: 5, agent: "researcher", tone: "injected" });
  });

  it("keeps only the newest 80 lines", () => {
    let s = initialState;
    for (let i = 1; i <= 90; i++) s = reduce(s, ev(i, { type: "data_progress", agent: "researcher", payload: { what: "x", percent: i } }));
    expect(s.feed).toHaveLength(80);
    expect(s.feed[0].seq).toBe(11);
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

describe("reduce: follow-up cards (M2)", () => {
  const req = (seq: number, id: string, reason: string) => ev(seq, { type: "followup_requested", agent: "naysayer", payload: { followup: id, reason } });
  const res = (seq: number, run: string, extra: object) => {
    const e = bt(seq, run, []);
    return { ...e, payload: { ...e.payload, ...extra } } as AuditEvent;
  };

  it("merges the backtest_result of F* into the requested card by id, keeping order", () => {
    let s = reduce(initialState, req(1, "F2", "years may disagree"));
    s = reduce(s, req(2, "F4", "one ticker"));
    s = reduce(s, res(3, "F4", { title: "Concentration", result: "r4", downgrade: true, cause: "F4 concentration: c" }));
    s = reduce(s, res(4, "F2", { title: "Per-year stability", result: "r2", downgrade: false, cause: null }));
    expect(s.followups).toEqual([
      { id: "F2", reason: "years may disagree", title: "Per-year stability", result: "r2", downgrade: false, cause: null },
      { id: "F4", reason: "one ticker", title: "Concentration", result: "r4", downgrade: true, cause: "F4 concentration: c" },
    ]);
    expect(s.followupsRun).toBe(2);
  });

  it("an M1 follow-up result without the new fields leaves the card as requested", () => {
    let s = reduce(initialState, req(1, "F2", "r"));
    s = reduce(s, bt(2, "F2", []));
    expect(s.followups).toEqual([{ id: "F2", reason: "r" }]);
  });

  it("ignores wrongly typed fields and still shows a result that arrives without a request", () => {
    const s = reduce(initialState, res(1, "F1", { title: 3, result: "skipped: no earnings data", downgrade: "yes", cause: 5 }));
    expect(s.followups).toEqual([{ id: "F1", reason: "", result: "skipped: no earnings data" }]);
  });

  it("keeps the backend's skipped flag", () => {
    const s = reduce(initialState, res(1, "F1", { result: "skipped: no earnings data", downgrade: false, cause: null, skipped: true }));
    expect(s.followups[0]).toMatchObject({ skipped: true, downgrade: false });
  });

  it("appliedDowngrade only reports a downgrade listed in the verdict", () => {
    const met = { id: "F4", reason: "", downgrade: true, cause: "F4 concentration: c" };
    const verdict = (downgrades: object[]) =>
      reduce(initialState, ev(1, { type: "verdict", agent: null, payload: { verdict: "inconclusive", reason: "r", headline: {}, downgrades } })).verdict;
    expect(appliedDowngrade(met, null)).toBeNull();
    expect(appliedDowngrade(met, verdict([{ cause: "tail risk", from: "promising", to: "inconclusive" }]))).toBeNull();
    expect(appliedDowngrade(met, verdict([{ cause: "F4 concentration: c", from: "promising", to: "inconclusive" }]))).toMatchObject({ to: "inconclusive" });
    expect(appliedDowngrade({ ...met, downgrade: false }, verdict([{ cause: "F4 concentration: c" }]))).toBeNull();
  });
});
