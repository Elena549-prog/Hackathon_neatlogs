"""Forward paper trading: the frozen swarm on days after the test split, with fresh prices.

Downloads the 5 tickers through the latest close into data/prices_live/ (the frozen
data/prices is never touched), builds features for every trading day after the test
split's last setup, and runs the same watcher and agents as src/swarm.py. Each approved
plan becomes a paper position: closed when the stop or target is hit or the 10 days are
up, otherwise open and marked at the latest close. Paper trades only; no orders anywhere.

    python -m src.forward              # writes results/paper_forward.{jsonl,md} and prints the ledger
"""
import argparse
import datetime as dt
import json
import os
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pandas as pd

from src.data import TICKERS, download_prices
from src.features import features_at
from src.labels import SETUPS_PATH, SPLITS
from src.simulator import first_hit
from src.swarm import decide, triggered
from src.tools import Market, prepare_prices

LIVE_DIR = os.path.join("data", "prices_live")
OUT = os.path.join("results", "paper_forward")


def forward_setups(raw_by_ticker, after=SPLITS[-1][2]):
    """Setups for every trading day after `after`, with features from data up to that day. No label."""
    rows = []
    for ticker, df in raw_by_ticker.items():
        for t, date in enumerate(df.index):
            if date <= pd.Timestamp(after):
                continue
            feats = features_at(df, t)
            if any(np.isnan(v) for v in feats.values()):
                continue
            rows.append({"ticker": ticker, "date": date.date().isoformat(), "split": "forward", "label": None, **feats})
    return rows


def position(plan, market, ticker, date):
    """The paper position as of the last price: closed (win, loss, expired) or open, marked at the last close."""
    close, high, low = market.arrays[ticker]
    t = market.row_index(ticker, date)
    days = min(plan["horizon_days"], len(close) - 1 - t)
    outcome, exit_price = first_hit(close, high, low, t, plan["entry"], plan["stop"], plan["target"], days)
    still_open = outcome == "expired" and days < plan["horizon_days"]   # not hit yet, days still to run
    return {"status": "open" if still_open else "closed", "trade_outcome": None if still_open else outcome,
            "pnl_pct": exit_price / plan["entry"] - 1, "days_held": days,
            "as_of": market.prices[ticker].index[t + days].date().isoformat()}


def ledger(records, last_close, cost):
    woken = [r for r in records if r["verdict"] != "skipped"]
    trades = [r for r in records if r["verdict"] == "approve"]
    lines = ["# Forward paper trading", "",
             "Frozen swarm (commit f953747) on every trading day after the test split, prices through %s. "
             "Paper trades only: +5%% target, -3%% stop, 10 trading days, no fees." % last_close, "",
             "| Item | Value |", "|---|---|",
             "| Setups watched | %d |" % len(records),
             "| Woken by the watcher | %d |" % len(woken),
             "| Approved (paper positions) | %d |" % len(trades),
             "| Errors | %d |" % sum(r["verdict"] == "error" for r in records),
             "| LLM cost | $%.4f |" % cost, "",
             "## Paper positions", ""]
    if trades:
        lines += ["| Decided | Ticker | Entry | Stop | Target | Status | P&L | Days | As of |",
                  "|---|---|---|---|---|---|---|---|---|"]
        for r in trades:
            p = r["plan"]
            lines.append("| %s | %s | %.2f | %.2f | %.2f | %s | %+.2f%% | %d/10 | %s |" % (
                r["date"], r["ticker"], p["entry"], p["stop"], p["target"],
                r["status"] + (" (%s)" % r["trade_outcome"] if r["trade_outcome"] else ""),
                100 * r["pnl_pct"], r["days_held"], r["as_of"]))
    else:
        lines.append("None: the swarm declined every woken setup.")
    lines += ["", "## Woken setups the swarm declined", "", "| Date | Ticker | Reason |", "|---|---|---|"]
    lines += ["| %s | %s | %s |" % (r["date"], r["ticker"], (r["objections"] or [r.get("error", "")])[0])
              for r in woken if r["verdict"] != "approve"]
    return "\n".join(lines) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args(argv)

    from src.llm import make_llm
    from src.tracing import make_tracer

    end = (dt.date.today() + dt.timedelta(days=1)).isoformat()      # exclusive
    os.makedirs(LIVE_DIR, exist_ok=True)
    raw = {}
    for t in TICKERS:
        raw[t] = download_prices(t, end=end)
        raw[t].to_csv(os.path.join(LIVE_DIR, "%s.csv" % t))
    market = Market({t: prepare_prices(df) for t, df in raw.items()}, pd.read_csv(SETUPS_PATH))
    last_close = min(df.index[-1] for df in raw.values()).date().isoformat()

    tracer = make_tracer(tags=("trading-swarm", "forward", "provider:deepseek"))
    llm = make_llm(tracer, "deepseek")

    def one(setup):
        base = {"ticker": setup["ticker"], "date": setup["date"], "split": "forward"}
        if not triggered(setup):
            return dict(base, rounds=0, verdict="skipped", plan=None, objections=[])
        try:
            rec = decide(setup, market, llm, tracer)
        except Exception as e:     # one bad setup must not stop the run
            return dict(base, rounds=None, verdict="error", plan=None, objections=[], error=repr(e))
        if rec["verdict"] == "approve":     # decided above; only now are later prices read
            rec.update(position(rec["plan"], market, setup["ticker"], setup["date"]))
        return rec

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        records = list(pool.map(one, forward_setups(raw)))
    tracer.flush()

    with open(OUT + ".jsonl", "w") as f:
        f.writelines(json.dumps(r) + "\n" for r in records)
    text = ledger(records, last_close, tracer.total_cost())
    with open(OUT + ".md", "w") as f:
        f.write(text)
    print(text)


if __name__ == "__main__":
    main()
