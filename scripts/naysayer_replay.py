"""Replay one Naysayer decision with the current prompt on the exact input an earlier run saw.

    python -m scripts.naysayer_replay results/posthoc_amzn_v1_naysayer.json

The input file holds the plan, facts and math the old Naysayer got (copied from its neatlogs
trace) and its verdict. Only the Naysayer call is repeated; the plan, facts and math are fixed.
If the new verdict is approve, the plan is paper-traded on real prices. Writes <input>_v2.json.
Post-hoc: the setup was already seen, so the result is a demo of the prompt change, not evidence.
"""
import json
import sys

from src.agents import mathematician, naysayer
from src.llm import make_llm
from src.simulator import simulate
from src.tools import backtest, load_market
from src.tracing import make_tracer


def main(path):
    case = json.load(open(path, encoding="utf-8"))
    tracer = make_tracer(tags=("trading-swarm", "naysayer-replay", "ticker:" + case["ticker"], "date:" + case["date"]))
    market = load_market()
    rec = [json.loads(l) for l in open("results/swarm_test.jsonl", encoding="utf-8")
           if '"%s", "date": "%s"' % (case["ticker"], case["date"]) in l][0]
    plan = rec["plan"]
    math = mathematician.run(plan, backtest(plan, market, case["date"]))   # code, so identical to the run
    assert {k: math[k] for k in ("n", "hit_rate_low")} == {k: case["input"]["math"][k] for k in ("n", "hit_rate_low")}
    verdict, objections = naysayer.run(make_llm(tracer, "deepseek"), case["input"]["plan"], case["input"]["facts"], math,
                                       round=2, ticker=case["ticker"], date=case["date"])
    tracer.flush()
    out = dict(case, v2_output={"verdict": verdict, "objections": objections}, llm_cost=tracer.total_cost())
    if verdict == "approve":
        out["paper_trade"] = dict(simulate(plan, market, case["ticker"], case["date"]),
                                  entry=plan["entry"], stop=plan["stop"], target=plan["target"])
    dest = path.replace(".json", "_v2.json")
    json.dump(out, open(dest, "w", encoding="utf-8"), indent=1)
    print(json.dumps({k: out[k] for k in ("v1_output", "v2_output", "llm_cost")} | {"paper_trade": out.get("paper_trade")}, indent=1))


if __name__ == "__main__":
    main(sys.argv[1])
