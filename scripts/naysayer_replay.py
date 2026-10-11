"""Replay one Naysayer decision with the current prompt on the exact input an earlier run saw.

    python -m scripts.naysayer_replay results/posthoc_amzn_v1_naysayer.json [out.json] [--events DIR]

The input file holds the plan, facts and math the old Naysayer got (copied from its neatlogs
trace) and its verdict. Only the Naysayer call is repeated; the plan, facts and math are fixed.
If the new verdict is approve, the plan is paper-traded on real prices. Writes out.json
(default <input>_v2.json) and prints each step as it happens. With --events DIR it also writes
DIR/events.jsonl in the audit event schema, so mission control can replay the decision.
Post-hoc: the setup was already seen, so the result is a demo of the prompt change, not evidence.
"""
import json
import logging
import sys
import time
from pathlib import Path

import pandas as pd

from src.agents import mathematician, naysayer
from src.auditor.eventlog import EventLog
from src.llm import make_llm
from src.simulator import simulate
from src.tools import backtest, load_market, matches, wilson_low
from src.tracing import make_tracer

RED, GREEN, AMBER, DIM, BOLD, OFF = "\033[31m", "\033[32m", "\033[33m", "\033[2m", "\033[1m", "\033[0m"
WIN, LOSS = 0.05, -0.03
# The recorded steps (facts, plan, gate) take no time here, so their events would all land in the same
# millisecond; this pause spaces them out for the replay. The Naysayer v2 call is live and keeps its real time.
PACE_S = 0.6


def say(text=""):
    print(text, flush=True)


class Events:
    """Audit-schema events for one decision; a no-op without a directory."""

    def __init__(self, directory, audit_id):
        self.log = None
        if directory:
            path = Path(directory) / "events.jsonl"
            path.unlink(missing_ok=True)       # one run per file
            self.log = EventLog(path, audit_id)

    def __call__(self, type_, agent, **payload):
        if self.log:
            self.log.emit(type_, agent, payload)
            time.sleep(PACE_S)


def stats(returns, dates):
    """Stats in the backtest_result shape for fixed +5%/-3% outcomes; 95% bounds from the Wilson interval."""
    s = pd.Series(returns, index=pd.to_datetime(dates)).sort_index()
    n, wins = len(s), int((s > 0).sum())
    low, high = wilson_low(wins, n), 1 - wilson_low(n - wins, n)
    blocks = s.groupby(s.index.to_period("M")).sum()     # calendar months as the blocks
    return {"n": n, "blocks": len(blocks), "win_rate": wins / n, "mean": float(s.mean()), "median": float(s.median()),
            "ci_low": low * WIN + (1 - low) * LOSS, "ci_high": high * WIN + (1 - high) * LOSS,
            "worst_trade": float(s.min()), "worst_window": float(blocks.min())}


def equity(returns, dates):
    s = pd.Series(returns, index=pd.to_datetime(dates)).sort_index().cumsum()
    return [[d.date().isoformat(), float(v)] for d, v in s.items()]


def main(path, dest=None, events_dir=None):
    logging.getLogger("neatlogs").setLevel(logging.WARNING)    # its INFO lines at exit only add noise
    case = json.load(open(path, encoding="utf-8"))
    t, d = case["ticker"], case["date"]
    ev = Events(events_dir, "trade-%s-%s" % (t.lower(), d))
    say(BOLD + "Naysayer replay: setup %s %s" % (t, d) + OFF)
    say(AMBER + "post-hoc: this setup was already seen in the test run; paper trade only" + OFF)
    ev("audit_started", None, idea="%s %s · swarm trade decision" % (t, d), trace_id=None, llm_budget=1, fault=None,
       provider="deepseek", kind="trade")
    tracer = make_tracer(tags=("trading-swarm", "naysayer-replay", "ticker:" + t, "date:" + d))
    market = load_market()
    prices = market.prices[t]
    i = market.row_index(t, d)

    say()
    say(BOLD + "[1] Researcher facts" + OFF + DIM + "  (from the test run's neatlogs trace; agents never see ticker or date)" + OFF)
    ev("agent_started", "researcher", step="data")
    ev("tool_called", "researcher", tool="get_prices", args={"lookback_days": 20})
    ev("tool_result", "researcher", tool="get_prices", ok=True, duration_ms=0, summary="last 20 closes, scaled so today = 100")
    for k in ("ret_1d", "ret_10d", "close_to_ma200"):
        say("    " + case["input"]["facts"][k])
    ev("agent_finished", "researcher", step="data", status="ok", duration_ms=0, summary={"facts": case["input"]["facts"]})

    rec = [json.loads(l) for l in open("results/swarm_test.jsonl", encoding="utf-8")
           if '"%s", "date": "%s"' % (t, d) in l][0]
    plan = rec["plan"]
    conditions = ", ".join("%s %s %s" % (k, op, v) for k, (op, v) in plan["conditions"].items())
    say()
    say(BOLD + "[2] Planner plan" + OFF)
    ev("agent_started", "planner", step="plan")
    say("    " + plan["thesis"])
    say("    conditions: " + conditions)
    say("    exits: +5% target, -3% stop, 10 trading days")
    ev("agent_finished", "planner", step="plan", status="ok", duration_ms=0,
       summary={"what_tested": "long on %s; exit at +5%% / -3%% / 10 days. Thesis: %s" % (conditions, plan["thesis"])})

    say()
    say(BOLD + "[3] Mathematician" + OFF + DIM + "  (code, re-run now)" + OFF)
    ev("agent_started", "mathematician", step="backtest")
    math = mathematician.run(plan, backtest(plan, market, d))   # code, so identical to the run
    assert {k: math[k] for k in ("n", "hit_rate_low")} == {k: case["input"]["math"][k] for k in ("n", "hit_rate_low")}
    train = market.setups[market.setups["split"] == "train"]
    known = train[(train["outcome_end"] < pd.Timestamp(d)).to_numpy()]
    past = known[matches(known, plan["conditions"])]
    past_ret = [WIN if x else LOSS for x in past["label"]]
    all_ret = [WIN if x else LOSS for x in known["label"]]
    def evidence(last_row):     # past matches, and this setup's close vs entry up to last_row (never past the decision first)
        curve = [[day.date().isoformat(), float(c / plan["entry"] - 1)] for day, c in prices["Adj Close"].iloc[i - 19:last_row + 1].items()]
        ev("backtest_result", "mathematician", run="base", train=stats(past_ret, past["date"]), validation=None,
           baseline=dict(stats(all_ret, known["date"]), paired_ci_low=None),
           equity_train=equity(past_ret, past["date"]), equity_validation=curve, histogram=None)
    evidence(i)
    say("    %d of %d past setups match · hit rate %.1f%% · cautious %.1f%% vs 37.5%% break-even"
        % (math["n"], math["eligible"], 100 * math["hit_rate"], 100 * math["hit_rate_low"]))
    say("    gate: " + GREEN + "PASSED" + OFF + "   expected value %+.2f%% per trade" % (100 * math["ev_pct"]))
    ev("agent_finished", "mathematician", step="backtest", status="ok", duration_ms=0,
       summary={"n": math["n"], "hit_rate": math["hit_rate"], "hit_rate_low": math["hit_rate_low"]})

    say()
    say(BOLD + "[4] Naysayer v1" + OFF + DIM + "  (recorded in the test run)" + OFF)
    ev("agent_started", "naysayer", step="review")
    ev("check_result", "naysayer", check="gate_evidence", passed=True, value=math["n"],
       note="%d comparable past setups (need at least 30)" % math["n"])
    ev("check_result", "naysayer", check="gate_breadth", passed=True, value=math["match_share"],
       note="matches %.1f%% of past setups (limit 80%%)" % (100 * math["match_share"]))
    ev("check_result", "naysayer", check="gate_edge", passed=True, value=math["hit_rate_low"],
       note="cautious hit rate %.1f%% vs 37.5%% break-even" % (100 * math["hit_rate_low"]))
    say("    " + RED + case["v1_output"]["verdict"].upper() + OFF)
    for o in case["v1_output"]["objections"]:
        say("    - " + o)
    ev("check_result", "naysayer", check="naysayer_v1", passed=case["v1_output"]["verdict"] == "approve", value=None,
       note=" ".join(case["v1_output"]["objections"]) or "no objections")

    say()
    say(BOLD + "[5] Naysayer v2" + OFF + DIM + "  (calling deepseek-v4-pro now, same input)" + OFF)
    verdict, objections = naysayer.run(make_llm(tracer, "deepseek"), case["input"]["plan"], case["input"]["facts"], math,
                                       round=2, ticker=t, date=d)
    tracer.flush()
    for s in tracer.spans:
        if s["kind"] == "llm":
            ev("llm_call", "naysayer", model=s["model"], prompt_tokens=s["prompt_tokens"],
               completion_tokens=s["completion_tokens"], cost_usd=s["cost"], latency_ms=int(1000 * s["duration"]))
    say("    " + (GREEN if verdict == "approve" else RED) + verdict.upper() + OFF + ("  (no objections)" if not objections else ""))
    for o in objections:
        say("    - " + o)
    ev("check_result", "naysayer", check="naysayer_v2", passed=verdict == "approve", value=None,
       note=" ".join(objections) or "no objections")
    ev("agent_finished", "naysayer", step="review", status="ok", duration_ms=0, summary={"verdict": verdict})
    out = dict(case, v2_output={"verdict": verdict, "objections": objections}, llm_cost=tracer.total_cost())

    if verdict == "approve":
        trade = simulate(plan, market, t, d)
        out["paper_trade"] = dict(trade, entry=plan["entry"], stop=plan["stop"], target=plan["target"])
        say()
        say(BOLD + "[6] Paper trade" + OFF + DIM + "  (opened at the close; later prices read only now)" + OFF)
        say("    LONG %d %s @ %.2f   stop %.2f   target %.2f"
            % (math["size"], t, plan["entry"], plan["stop"], plan["target"]))
        days = 0
        for days in range(1, plan["horizon_days"] + 1):
            row = prices.iloc[i + days]
            say("    day %d  %s  high %.2f  low %.2f" % (days, prices.index[i + days].date(), row["High"], row["Low"]))
            if row["Low"] <= plan["stop"] or row["High"] >= plan["target"]:
                break
        evidence(i + days)
        usd = math["size"] * plan["entry"] * trade["pnl_pct"]
        color = GREEN if trade["pnl_pct"] > 0 else RED
        say("    " + color + BOLD + "%s %+.2f%%  (%+.0f USD on paper)" % (trade["trade_outcome"].upper(), 100 * trade["pnl_pct"], usd) + OFF)
        ev("verdict", None, verdict="trade", reason="Naysayer v2 approved: long %d %s at %.2f, stop %.2f, target %.2f. %s on day %d."
           % (math["size"], t, plan["entry"], plan["stop"], plan["target"], trade["trade_outcome"].capitalize(), days),
           headline={"entry": plan["entry"], "exit": plan["entry"] * (1 + trade["pnl_pct"]), "days": days,
                     "pnl": trade["pnl_pct"], "usd": usd},
           downgrades=[])
    else:
        ev("verdict", None, verdict="no_trade", reason=" ".join(objections), headline={}, downgrades=[])

    dest = dest or path.replace(".json", "_v2.json")
    json.dump(out, open(dest, "w", encoding="utf-8"), indent=1)
    say()
    say(DIM + "LLM cost $%.4f · saved %s" % (out["llm_cost"], dest) + OFF)


if __name__ == "__main__":
    args = sys.argv[1:]
    events_dir = None
    if "--events" in args:
        k = args.index("--events")
        events_dir = args[k + 1]
        del args[k:k + 2]
    main(*args[:2], events_dir=events_dir)
