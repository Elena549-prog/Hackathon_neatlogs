"""Step 5: the four-agent swarm. One decision line per setup, then a summary.

For each setup: Researcher -> Planner -> Mathematician -> Naysayer. A block sends the
objections back to the Planner, up to MAX_ROUNDS rounds; then the setup is dropped.
Approved plans become paper trades, closed by the simulator only after the decision
is logged. Agents never see the label, the ticker, the date, or raw price levels.

    python -m src.swarm --split validation --limit 5     # smoke run
    python -m src.swarm --split validation               # baseline run
"""
import argparse
import json
import os
from concurrent.futures import ThreadPoolExecutor

import numpy as np

from src.agents import mathematician, naysayer, planner, researcher
from src.features import FEATURE_NAMES
from src.simulator import simulate
from src.tools import backtest, get_prices

MAX_ROUNDS = 2
LOOKBACK = 20
SUMMARY_PATH = os.path.join("runs", "swarm_summary.md")


def normalized(plan):
    """The plan as the agents see it: entry scaled to 100, no ticker."""
    scale = 100.0 / plan["entry"]
    return {"entry": 100.0, "stop": round(plan["stop"] * scale, 4),
            "target": round(plan["target"] * scale, 4), "horizon_days": plan["horizon_days"],
            "thesis": plan["thesis"], "conditions": plan["conditions"],
            "facts_cited": plan["facts_cited"]}


def decide(setup, market, llm, tracer):
    """Run the agents on one setup. Returns the decision record (no outcome yet)."""
    ticker, date = setup["ticker"], setup["date"]
    tags = {"ticker": ticker, "date": date}
    features = {k: float(setup[k]) for k in FEATURE_NAMES}
    with tracer.span("workflow", "swarm", **tags):
        with tracer.span("tool", "get_prices", agent="researcher", round=0, **tags) as rec:
            recent = get_prices(market, ticker, date, LOOKBACK)
            entry = float(recent["Adj Close"].iloc[-1])
            closes = [round(100 * c / entry, 2) for c in recent["Adj Close"]]
            rec["input"], rec["output"] = {"lookback_days": LOOKBACK}, closes
        facts = researcher.run(llm, features, closes, round=0, **tags)

        objections, plan, verdict, rnd = [], None, "block", 0
        for rnd in range(1, MAX_ROUNDS + 1):
            raw = planner.run(llm, features, facts, objections, round=rnd, **tags)
            plan, err = planner.build(raw, ticker, entry, facts, features)
            if err:
                verdict, objections = "block", ["invalid plan: " + err]
                continue
            with tracer.span("tool", "backtest", agent="mathematician", round=rnd, **tags) as rec:
                bt = backtest(plan, market, date)
                rec["input"], rec["output"] = normalized(plan), bt
            with tracer.span("agent", "mathematician", agent="mathematician", round=rnd, **tags) as rec:
                math = mathematician.run(plan, bt)
                rec["input"], rec["output"] = bt, math
            verdict, objections = naysayer.run(llm, normalized(plan), facts, math, round=rnd, **tags)
            if verdict == "approve":
                break
    return {"ticker": ticker, "date": date, "split": setup["split"], "rounds": rnd,
            "verdict": "approve" if verdict == "approve" else "dropped",
            "plan": plan, "objections": objections}


def run(split, market, llm, tracer, limit=None, out_path=None, workers=1):
    """Decide every setup in `split`, simulate approved trades, write JSONL. Returns the records.

    With workers > 1, setups are decided in parallel threads; lines are still written in
    setup order, each as soon as it and every earlier setup are done.
    """
    if split == "test":
        raise SystemExit("The swarm step does not run on the test split.")
    rows = market.setups[market.setups["split"] == split]
    if limit:
        rows = rows.head(limit)
    out_path = out_path or os.path.join("runs", "swarm_%s.jsonl" % split)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    def one(setup):
        try:
            rec = decide(setup, market, llm, tracer)
        except Exception as e:     # one bad setup must not stop the run; it is logged as an error
            rec = {"ticker": setup["ticker"], "date": setup["date"], "split": split,
                   "rounds": None, "verdict": "error", "plan": None, "objections": [],
                   "error": repr(e)}
        # The decision is fixed above. Only now does anything read prices after the setup date.
        if rec["verdict"] == "approve":
            rec.update(simulate(rec["plan"], market, setup["ticker"], setup["date"]))
        else:
            rec.update(trade_outcome=None, pnl_pct=None)
        rec["label"] = int(setup["label"])   # for scoring only; agents never saw it
        return rec

    records = []
    with open(out_path, "w") as f, ThreadPoolExecutor(max_workers=workers) as pool:
        for rec in pool.map(one, rows.to_dict("records")):   # map keeps setup order
            f.write(json.dumps(rec) + "\n")
            f.flush()
            records.append(rec)
    return records


def summarize(records, market, split, cost=0.0, seed=0):
    """Markdown summary: swarm vs random approvals vs always-approve vs buy-and-hold."""
    labels = np.array([r["label"] for r in records])
    approved = [r for r in records if r["verdict"] == "approve"]
    n, k = len(records), len(approved)
    rate = k / n if n else 0.0
    rng = np.random.default_rng(seed)
    random_pick = rng.random(n) < rate                      # same approval rate as the swarm
    dates = market.setups.loc[market.setups["split"] == split, "date"]
    bh = [market.prices[t].loc[dates.min():dates.max(), "Adj Close"] for t in market.prices]
    bh_return = float(np.mean([s.iloc[-1] / s.iloc[0] - 1 for s in bh]))

    def pct(x):
        return "n/a" if x is None else "%.1f%%" % (100 * x)

    lines = [
        "# Swarm summary: %s split" % split, "",
        "| Item | Value |", "|---|---|",
        "| Setups | %d |" % n,
        "| Approved | %d (%s) |" % (k, pct(rate)),
        "| Dropped after %d rounds | %d |" % (MAX_ROUNDS, sum(r["verdict"] == "dropped" for r in records)),
        "| Errors | %d |" % sum(r["verdict"] == "error" for r in records),
        "| LLM cost | $%.4f |" % cost, "",
        "## Precision of approved trades (share that hit +5% before -3%)", "",
        "| Method | Approved | Precision |", "|---|---|---|",
        "| Swarm | %d | %s |" % (k, pct(np.mean([r["trade_outcome"] == "win" for r in approved]) if k else None)),
        "| Random, same approval rate (seed %d) | %d | %s |" % (seed, random_pick.sum(), pct(labels[random_pick].mean() if random_pick.any() else None)),
        "| Always approve (= base rate) | %d | %s |" % (n, pct(labels.mean() if n else None)), "",
        "Mean P&L per approved trade: %s." % pct(np.mean([r["pnl_pct"] for r in approved]) if k else None),
        "Buy-and-hold over the split, mean across tickers: %s." % pct(bh_return), "",
        "Notes: no fees or slippage. Every plan uses the fixed +5%/-3%/10-day levels, so swarm",
        "outcomes and labels score the same bet. Break-even precision is 37.5%.",
        "Fewer than 50 approved trades: read as directional only.",
    ]
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--split", default="validation", choices=["train", "validation"])
    parser.add_argument("--limit", type=int, help="only the first N setups (smoke run)")
    parser.add_argument("--out", help="JSONL path (default runs/swarm_<split>.jsonl)")
    parser.add_argument("--workers", type=int, default=1, help="setups decided in parallel")
    parser.add_argument("--provider", default="deepseek", choices=["deepseek", "claude"],
                        help="deepseek needs DEEPSEEK_API_KEY; claude needs ANTHROPIC_API_KEY")
    args = parser.parse_args()

    from src.llm import make_llm
    from src.tools import load_market
    from src.tracing import make_tracer

    market = load_market()
    tracer = make_tracer(tags=("trading-swarm", "provider:" + args.provider))
    records = run(args.split, market, make_llm(tracer, args.provider), tracer, args.limit, args.out,
                  args.workers)
    tracer.flush()
    summary = summarize(records, market, args.split, cost=tracer.total_cost())
    with open(SUMMARY_PATH, "w") as f:
        f.write(summary)
    print(summary)


if __name__ == "__main__":
    main()
