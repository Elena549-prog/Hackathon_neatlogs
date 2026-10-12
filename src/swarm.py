"""Step 5: the four-agent swarm. One decision line per setup, then a summary.

A price watcher wakes the swarm only on an unusual move (see triggered()); other setups
are logged as skipped, with no LLM call. For each triggered setup: Researcher -> Planner
-> Mathematician -> Naysayer. A fixable block sends the objections back to the Planner,
up to MAX_ROUNDS rounds; then the setup is dropped. Approved plans become paper trades,
closed by the simulator only after the decision is logged. Agents never see the label,
the ticker, the date, or raw price levels.

    python -m src.swarm --split validation --limit 5     # smoke run
    python -m src.swarm --setup GOOGL:2026-05-29         # one setup, decided and paper-traded (demo)
    python -m src.swarm --split validation               # baseline run
    python -m src.swarm --split test --final-test        # the one test run, frozen config; never repeated
    python -m src.swarm --split test --final-test --resume   # only to finish that run if it stopped
    python -m src.swarm --split test --post-hoc --setup AMZN:2026-07-30   # re-run one already-seen test setup (demo, not evidence)
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
WATCH_SIGMA = 1.5   # wake the swarm when |1-day return| >= 1.5 x 20-day volatility (fires on ~12% of train days)
SUMMARY_PATH = os.path.join("runs", "swarm_summary.md")
TEST_RESULTS = [os.path.join("results", f) for f in ("swarm_test_summary.md", "swarm_test.jsonl")]


def triggered(setup):
    """The price watcher: an unusual 1-day move, up or down. Uses only data at or before the setup day."""
    return abs(setup["ret_1d"]) >= WATCH_SIGMA * setup["vol_20d"]


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
            if verdict == "approve" or not naysayer.retryable(math):
                break
    return {"ticker": ticker, "date": date, "split": setup["split"], "rounds": rnd,
            "verdict": "approve" if verdict == "approve" else "dropped",
            "plan": plan, "objections": objections}


def run(split, market, llm, tracer, limit=None, out_path=None, workers=1, resume=False, final_test=False,
        setup=None, post_hoc=False):
    """Decide every setup in `split` (or only `setup`, a (ticker, date) pair), simulate approved
    trades, write JSONL. Returns the records. post_hoc re-runs one test setup after the one test
    run; its output is named posthoc and never replaces the test result.

    With workers > 1, setups are decided in parallel threads; lines are still written in
    setup order. With resume, setups already in out_path (or in out_path.tmp, left by an
    interrupted run) without an error are kept as they are and only the rest are decided.
    Output goes to a temp file that replaces out_path at the end, so an interrupted run
    never destroys earlier results. The test split needs final_test: one full run, never
    a second one over an existing result.
    """
    if post_hoc and (final_test or not setup):
        raise SystemExit("--post-hoc re-runs one already-seen setup: it needs --setup and not --final-test.")
    if split == "test" and not (final_test or post_hoc):
        raise SystemExit("The swarm runs on the test split only once, with --final-test.")
    name = "_".join([split, *(["posthoc"] if post_hoc else []), *setup]) if setup else split
    out_path = out_path or os.path.join("runs", "swarm_%s.jsonl" % name)
    tmp_path = out_path + ".tmp"
    if final_test:
        if split != "test":
            raise SystemExit("--final-test needs --split test.")
        if limit or setup:
            raise SystemExit("--final-test is one full run: --limit and --setup are not allowed.")
        for path in TEST_RESULTS:
            if os.path.exists(path):
                raise SystemExit("%s exists: the test split has been run. Do not run it again." % path)
        for path in (out_path, tmp_path):
            if os.path.exists(path) and not resume:
                raise SystemExit("%s exists: use --resume to finish that run, never start a second one." % path)
    rows = market.setups[market.setups["split"] == split]
    if setup:
        rows = rows[(rows["ticker"] == setup[0]) & (rows["date"] == setup[1])]
        if rows.empty:
            raise SystemExit("no setup %s %s in the %s split" % (*setup, split))
    if limit:
        rows = rows.head(limit)
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)

    done = {}
    for path in (out_path, tmp_path) if resume else ():
        if os.path.exists(path):
            with open(path) as f:
                for line in f:
                    try:
                        r = json.loads(line)
                    except ValueError:      # a last line cut off when the run was killed
                        continue
                    if r["verdict"] != "error":
                        done[(r["ticker"], r["date"])] = r

    def one(setup):
        if (setup["ticker"], setup["date"]) in done:
            return done[(setup["ticker"], setup["date"])]
        if not triggered(setup):    # no unusual move: the watcher doesn't wake the swarm, no LLM call
            return {"ticker": setup["ticker"], "date": setup["date"], "split": split, "rounds": 0,
                    "verdict": "skipped", "plan": None, "objections": [], "trade_outcome": None,
                    "pnl_pct": None, "label": int(setup["label"])}
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
    with open(tmp_path, "w") as f, ThreadPoolExecutor(max_workers=workers) as pool:
        for rec in pool.map(one, rows.to_dict("records")):   # map keeps setup order
            f.write(json.dumps(rec) + "\n")
            f.flush()
            records.append(rec)
    os.replace(tmp_path, out_path)
    return records


def summarize(records, market, split, cost=0.0, seed=0):
    """Markdown summary: swarm vs random approvals vs always-approve vs buy-and-hold."""
    labels = np.array([r["label"] for r in records])
    woke = np.array([r["verdict"] != "skipped" for r in records])
    approved = [r for r in records if r["verdict"] == "approve"]
    n, k, n_woke = len(records), len(approved), int(woke.sum())
    rate = k / n_woke if n_woke else 0.0
    rng = np.random.default_rng(seed)
    random_pick = woke & (rng.random(n) < rate)               # same approval rate, among the same setups
    dates = market.setups.loc[market.setups["split"] == split, "date"]
    bh = [market.prices[t].loc[dates.min():dates.max(), "Adj Close"] for t in market.prices]
    bh_return = float(np.mean([s.iloc[-1] / s.iloc[0] - 1 for s in bh]))

    def pct(x):
        return "n/a" if x is None else "%.1f%%" % (100 * x)

    lines = [
        "# Swarm summary: %s split" % split, "",
        "| Item | Value |", "|---|---|",
        "| Setups | %d |" % n,
        "| Watcher woke the swarm (1-day move at least %.1f x 20-day vol) | %d (%s) |" % (WATCH_SIGMA, n_woke, pct(n_woke / n if n else None)),
        "| Skipped by the watcher (no LLM call) | %d |" % (n - n_woke),
        "| Approved | %d (%s of woken) |" % (k, pct(rate)),
        "| Dropped | %d |" % sum(r["verdict"] == "dropped" for r in records),
        "| Errors | %d |" % sum(r["verdict"] == "error" for r in records),
        "| LLM cost | $%.4f (%s per woken setup) |" % (cost, "$%.4f" % (cost / n_woke) if n_woke else "n/a"), "",
        "## Precision of approved trades (share that hit +5% before -3%)", "",
        "| Method | Approved | Precision |", "|---|---|---|",
        "| Swarm | %d | %s |" % (k, pct(np.mean([r["trade_outcome"] == "win" for r in approved]) if k else None)),
        "| Random, same approval rate among woken setups (seed %d) | %d | %s |" % (seed, random_pick.sum(), pct(labels[random_pick].mean() if random_pick.any() else None)),
        "| Always approve woken setups | %d | %s |" % (n_woke, pct(labels[woke].mean() if n_woke else None)),
        "| Always approve every setup (= base rate) | %d | %s |" % (n, pct(labels.mean() if n else None)), "",
        "Mean P&L per approved trade: %s." % pct(np.mean([r["pnl_pct"] for r in approved]) if k else None),
        "Buy-and-hold over the split, mean across tickers: %s." % pct(bh_return), "",
        "Notes: no fees or slippage. Every plan uses the fixed +5%/-3%/10-day levels, so swarm",
        "outcomes and labels score the same bet. Break-even precision is 37.5%.",
        "Fewer than 50 approved trades: read as directional only.",
    ]
    return "\n".join(lines) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--split", default="validation", choices=["train", "validation", "test"])
    parser.add_argument("--limit", type=int, help="only the first N setups (smoke run)")
    parser.add_argument("--out", help="JSONL path (default runs/swarm_<split>.jsonl)")
    parser.add_argument("--workers", type=int, default=1, help="setups decided in parallel")
    parser.add_argument("--resume", action="store_true",
                        help="keep finished setups from --out and re-decide only errors and missing ones")
    parser.add_argument("--final-test", action="store_true",
                        help="allow the one full run on --split test; refuses --limit, --setup and any existing test result")
    parser.add_argument("--setup", metavar="TICKER:DATE", type=lambda s: tuple(s.split(":")),
                        help="decide only this setup of --split, e.g. GOOGL:2026-05-29, and print its record")
    parser.add_argument("--post-hoc", action="store_true",
                        help="with --split test and --setup: re-run one setup already seen in the test run (a demo, not evidence)")
    parser.add_argument("--provider", default="deepseek", choices=["deepseek", "claude"],
                        help="deepseek needs DEEPSEEK_API_KEY; claude needs ANTHROPIC_API_KEY")
    args = parser.parse_args(argv)
    if args.setup and len(args.setup) != 2:
        parser.error("--setup takes TICKER:DATE, e.g. GOOGL:2026-05-29")

    from src.llm import make_llm
    from src.tools import load_market
    from src.tracing import make_tracer

    market = load_market()
    tracer = make_tracer(tags=("trading-swarm", "provider:" + args.provider))
    records = run(args.split, market, make_llm(tracer, args.provider), tracer, args.limit, args.out,
                  args.workers, args.resume, final_test=args.final_test, setup=args.setup, post_hoc=args.post_hoc)
    tracer.flush()
    if args.setup:
        print(json.dumps(records[0], indent=1))
    summary = summarize(records, market, args.split, cost=tracer.total_cost())
    with open(SUMMARY_PATH, "w") as f:
        f.write(summary)
    print(summary)


if __name__ == "__main__":
    main()
