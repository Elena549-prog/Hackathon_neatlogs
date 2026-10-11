"""Replay one Naysayer decision with the current prompt on the exact input an earlier run saw.

    python -m scripts.naysayer_replay results/posthoc_amzn_v1_naysayer.json [out.json]

The input file holds the plan, facts and math the old Naysayer got (copied from its neatlogs
trace) and its verdict. Only the Naysayer call is repeated; the plan, facts and math are fixed.
If the new verdict is approve, the plan is paper-traded on real prices. Writes out.json
(default <input>_v2.json) and prints each step as it happens.
Post-hoc: the setup was already seen, so the result is a demo of the prompt change, not evidence.
"""
import json
import logging
import sys

from src.agents import mathematician, naysayer
from src.llm import make_llm
from src.simulator import simulate
from src.tools import backtest, load_market
from src.tracing import make_tracer

RED, GREEN, AMBER, DIM, BOLD, OFF = "\033[31m", "\033[32m", "\033[33m", "\033[2m", "\033[1m", "\033[0m"


def say(text=""):
    print(text, flush=True)


def main(path, dest=None):
    logging.getLogger("neatlogs").setLevel(logging.WARNING)    # its INFO lines at exit only add noise
    case = json.load(open(path, encoding="utf-8"))
    t, d = case["ticker"], case["date"]
    say(BOLD + "Naysayer replay: setup %s %s" % (t, d) + OFF)
    say(AMBER + "post-hoc: this setup was already seen in the test run; paper trade only" + OFF)
    tracer = make_tracer(tags=("trading-swarm", "naysayer-replay", "ticker:" + t, "date:" + d))
    market = load_market()

    say()
    say(BOLD + "[1] Researcher facts" + OFF + DIM + "  (from the test run's neatlogs trace; agents never see ticker or date)" + OFF)
    for k in ("ret_1d", "ret_10d", "close_to_ma200"):
        say("    " + case["input"]["facts"][k])

    rec = [json.loads(l) for l in open("results/swarm_test.jsonl", encoding="utf-8")
           if '"%s", "date": "%s"' % (t, d) in l][0]
    plan = rec["plan"]
    say()
    say(BOLD + "[2] Planner plan" + OFF)
    say("    " + plan["thesis"])
    say("    conditions: " + ", ".join("%s %s %s" % (k, op, v) for k, (op, v) in plan["conditions"].items()))
    say("    exits: +5% target, -3% stop, 10 trading days")

    say()
    say(BOLD + "[3] Mathematician" + OFF + DIM + "  (code, re-run now)" + OFF)
    math = mathematician.run(plan, backtest(plan, market, d))   # code, so identical to the run
    assert {k: math[k] for k in ("n", "hit_rate_low")} == {k: case["input"]["math"][k] for k in ("n", "hit_rate_low")}
    say("    %d of %d past setups match · hit rate %.1f%% · cautious %.1f%% vs 37.5%% break-even"
        % (math["n"], math["eligible"], 100 * math["hit_rate"], 100 * math["hit_rate_low"]))
    say("    gate: " + GREEN + "PASSED" + OFF + "   expected value %+.2f%% per trade" % (100 * math["ev_pct"]))

    say()
    say(BOLD + "[4] Naysayer v1" + OFF + DIM + "  (recorded in the test run)" + OFF)
    say("    " + RED + case["v1_output"]["verdict"].upper() + OFF)
    for o in case["v1_output"]["objections"]:
        say("    - " + o)

    say()
    say(BOLD + "[5] Naysayer v2" + OFF + DIM + "  (calling deepseek-v4-pro now, same input)" + OFF)
    verdict, objections = naysayer.run(make_llm(tracer, "deepseek"), case["input"]["plan"], case["input"]["facts"], math,
                                       round=2, ticker=t, date=d)
    tracer.flush()
    say("    " + (GREEN if verdict == "approve" else RED) + verdict.upper() + OFF + ("  (no objections)" if not objections else ""))
    for o in objections:
        say("    - " + o)
    out = dict(case, v2_output={"verdict": verdict, "objections": objections}, llm_cost=tracer.total_cost())

    if verdict == "approve":
        trade = simulate(plan, market, t, d)
        out["paper_trade"] = dict(trade, entry=plan["entry"], stop=plan["stop"], target=plan["target"])
        say()
        say(BOLD + "[6] Paper trade" + OFF + DIM + "  (opened at the close; later prices read only now)" + OFF)
        say("    LONG %d %s @ %.2f   stop %.2f   target %.2f"
            % (math["size"], t, plan["entry"], plan["stop"], plan["target"]))
        prices = market.prices[t]
        i = market.row_index(t, d)
        for day in range(1, plan["horizon_days"] + 1):
            row = prices.iloc[i + day]
            say("    day %d  %s  high %.2f  low %.2f" % (day, prices.index[i + day].date(), row["High"], row["Low"]))
            if row["Low"] <= plan["stop"] or row["High"] >= plan["target"]:
                break
        color = GREEN if trade["pnl_pct"] > 0 else RED
        say("    " + color + BOLD + "%s %+.2f%%  (%+.0f USD on paper)" % (trade["trade_outcome"].upper(), 100 * trade["pnl_pct"],
                                                                    math["size"] * plan["entry"] * trade["pnl_pct"]) + OFF)

    dest = dest or path.replace(".json", "_v2.json")
    json.dump(out, open(dest, "w", encoding="utf-8"), indent=1)
    say()
    say(DIM + "LLM cost $%.4f · saved %s" % (out["llm_cost"], dest) + OFF)


if __name__ == "__main__":
    main(*sys.argv[1:3])
