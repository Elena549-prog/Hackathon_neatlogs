"""Backtest (AUDITOR_SPEC section 2 trade rules, section 3 splits).

stock_long: entry at the setup day's Adj Close; stop and target are absolute prices; Open/High/Low are
scaled to the Adj Close scale; a gap through the stop or target fills at the Open; otherwise the first-hit
rule with the stop first on a same-day double hit; no hit by the horizon exits at that day's Adj Close.
Straddles: hold 10 days, payoff on split-adjusted Close, cost from the ATM formula with the section 2
haircuts. One open trade per ticker; a new entry only after the previous trade has closed.
"""
import numpy as np
import pandas as pd

from src.tools import matches

TRAIN = ("2015-01-01", "2025-12-31")
STRADDLE_TRAIN_START = "2020-01-01"
VALID = ("2026-01-01", "2026-06-30")
CUTOFF = pd.Timestamp("2026-01-01")        # a train trade must exit before this
HOLD = 10
COST_K, BUY_HAIRCUT, EARNINGS_FACTOR, SELL_HAIRCUT = 0.7979, 1.05, 1.20, 0.95
STRICTER_BUY, STRICTER_SELL = 1.10, 0.90
TRADE_COLUMNS = ["ticker", "entry_date", "exit_date", "entry", "exit", "ret"]


def split_window(family, split):
    if split == "validation":
        return pd.Timestamp(VALID[0]), pd.Timestamp(VALID[1])
    if split == "train":
        start = STRADDLE_TRAIN_START if family.startswith("straddle") else TRAIN[0]
        return pd.Timestamp(start), pd.Timestamp(TRAIN[1])
    raise ValueError("unknown split %r (the test split is never constructed)" % split)


def select_setups(features, plan, split):
    """Rows in the split's window whose features satisfy the plan's conditions (NaN never matches)."""
    start, end = split_window(plan["family"], split)
    f = features[(features["date"] >= start) & (features["date"] <= end)]
    conds = plan["conditions"]
    if conds:
        f = f.dropna(subset=list(conds))
        f = f[matches(f, conds)]
    return f.sort_values(["ticker", "date"])


def _positions(df, dates):
    return df.index.get_indexer(pd.DatetimeIndex(dates))


def stock_long_trades(prices, features, plan, split, stricter=False):
    e = plan["exit"]
    horizon, target_pct, stop_pct = int(e["horizon_days"]), float(e["target_pct"]), float(e["stop_pct"])
    setups = select_setups(features, plan, split)
    rows, drops = [], {"exit_after_cutoff": 0, "exit_past_data": 0}
    for ticker, grp in setups.groupby("ticker", sort=True):
        df = prices[ticker]
        adj = df["Adj Close"].to_numpy(float)
        factor = adj / df["Close"].to_numpy(float)
        op, hi, lo = (df[c].to_numpy(float) * factor for c in ("Open", "High", "Low"))
        dates, n = df.index, len(df)
        open_until = -1
        for pos in _positions(df, grp["date"]):
            if pos < 0 or pos <= open_until:
                continue
            entry = adj[pos]
            stop, target = entry * (1 - stop_pct), entry * (1 + target_pct)
            exit_price = exit_pos = None
            for i in range(pos + 1, min(pos + horizon, n - 1) + 1):
                if op[i] <= stop or op[i] >= target:
                    exit_price, exit_pos = op[i], i
                elif lo[i] <= stop:
                    exit_price, exit_pos = stop, i
                elif hi[i] >= target:
                    exit_price, exit_pos = target, i
                if exit_pos is not None:
                    break
            if exit_pos is None:
                if pos + horizon >= n:
                    drops["exit_past_data"] += 1
                    continue
                exit_price, exit_pos = adj[pos + horizon], pos + horizon
            if split == "train" and dates[exit_pos] >= CUTOFF:
                drops["exit_after_cutoff"] += 1
                continue
            open_until = exit_pos
            rows.append({"ticker": ticker, "entry_date": dates[pos], "exit_date": dates[exit_pos],
                         "entry": float(entry), "exit": float(exit_price), "ret": float(exit_price / entry - 1)})
    return pd.DataFrame(rows, columns=TRADE_COLUMNS), drops


def straddle_trades(prices, features, plan, split, earnings, stricter=False):
    buyer = plan["family"] == "straddle_buy"
    setups = select_setups(features, plan, split)
    rows = []
    drops = {"exit_after_cutoff": 0, "exit_past_data": 0, "stale_iv": 0, "earnings_in_window": 0}
    for ticker, grp in setups.groupby("ticker", sort=True):
        df = prices[ticker]
        close = df["Close"].to_numpy(float)
        dates, n = df.index, len(df)
        earn_pos = set(int(p) for p in df.index.searchsorted(pd.DatetimeIndex(earnings.get(ticker) or [])))
        open_until = -1
        for pos, iv in zip(_positions(df, grp["date"]), grp["iv"].to_numpy(float)):
            if pos < 0 or pos <= open_until:
                continue
            if not np.isfinite(iv):
                drops["stale_iv"] += 1
                continue
            if pos + HOLD >= n:
                drops["exit_past_data"] += 1
                continue
            exit_pos = pos + HOLD
            if split == "train" and dates[exit_pos] >= CUTOFF:
                drops["exit_after_cutoff"] += 1
                continue
            open_until = exit_pos
            formula = COST_K * iv * np.sqrt(HOLD / 252)
            payoff = abs(close[exit_pos] / close[pos] - 1)
            has_earnings = any(pos < ep <= exit_pos for ep in earn_pos)
            row = {"ticker": ticker, "entry_date": dates[pos], "exit_date": dates[exit_pos],
                   "entry": float(close[pos]), "exit": float(close[exit_pos])}
            if buyer:
                cost = formula * BUY_HAIRCUT * (EARNINGS_FACTOR if has_earnings else 1.0) * (STRICTER_BUY if stricter else 1.0)
                drops["earnings_in_window"] += int(has_earnings)
                row.update(cost=float(cost), ret=float(payoff / cost - 1))
            else:
                premium = formula * SELL_HAIRCUT * (STRICTER_SELL if stricter else 1.0)
                drops["earnings_in_window"] += int(has_earnings)
                row.update(premium=float(premium), ret=float((premium - payoff) / premium))
            rows.append(row)
    cols = TRADE_COLUMNS + (["cost"] if buyer else ["premium"])
    return pd.DataFrame(rows, columns=cols), drops


def run_backtest(prices, features, plan, earnings, split, stricter=False):
    """-> (trades, drops) for the plan's family on one split."""
    if plan["family"] == "stock_long":
        return stock_long_trades(prices, features, plan, split, stricter)
    return straddle_trades(prices, features, plan, split, earnings, stricter)
