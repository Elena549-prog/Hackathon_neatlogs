"""Mathematician (code): leakage-safe backtests on train and validation (spec sections 2, 3).

Trade rules:
- One open trade per ticker: a new entry is taken only on a day after the previous trade closed.
- stock_long: entry at the setup day's Adj Close; stop and target are absolute prices. Each day after
  entry: Open at or below the stop -> exit at the Open; Open at or above the target -> exit at the
  Open; else first hit of stop or target (stop first when both hit the same day); else exit at the
  horizon day's close. High, Low and Open are on the Adj Close scale.
- Straddles: hold 10 trading days. Payoff = |Close(t+10) / Close(t) - 1| on split-adjusted Close.
  Formula = 0.7979 x IV x sqrt(10/252). Buyer cost = formula x 1.05 (x 1.20 with an earnings date in
  the window); return = payoff / cost - 1. Seller premium = formula x 0.95; return = (premium - payoff)
  / premium. Trades with implied vol older than 5 calendar days are skipped and counted.

Splits: train setups 2015-01-01..2025-12-31 (straddles from 2020-01-01), dropped when the horizon
end is on or after 2026-01-01; validation setups 2026-01-01..2026-06-30, dropped when the horizon
end is past the data. The horizon end (not the actual exit) decides, so which setups exist never
depends on their outcome. The test window is never constructed.
"""
import math
import operator

import numpy as np
import pandas as pd

from src.auditor.data import (LeakageError, STRADDLE_TRAIN_START, TRAIN_END, TRAIN_START, VALID_END,
                              VALID_START)
from src.auditor.plan import STRADDLES

OPS = {">": operator.gt, "<": operator.lt, ">=": operator.ge, "<=": operator.le}
STRADDLE_HOLD = 10
ATM = 0.7979
BUY_HAIRCUT, SELL_HAIRCUT, EARNINGS_COST = 1.05, 0.95, 1.20


def horizon_of(plan, horizon=None):
    if horizon is not None:
        return horizon
    return plan["exit"]["horizon_days"] if plan["family"] == "stock_long" else STRADDLE_HOLD


def stock_exit(o, h, l, c, i, horizon, stop, target):
    """(exit index, exit price) for a long entered at row i's close. Gap-aware first-hit rule."""
    last = min(i + horizon, len(c) - 1)
    for j in range(i + 1, last + 1):
        if not math.isnan(o[j]):
            if o[j] <= stop:
                return j, o[j]
            if o[j] >= target:
                return j, o[j]
        if l[j] <= stop:            # stop first when both are hit on the same day
            return j, stop
        if h[j] >= target:
            return j, target
    return last, c[last]


def straddle_return(family, iv, payoff, earnings_in_window, cost_bump=0.0):
    """(return, premium or cost as a share of price) for one straddle."""
    formula = ATM * iv * math.sqrt(STRADDLE_HOLD / 252)
    if family == "straddle_buy":
        cost = formula * BUY_HAIRCUT * (EARNINGS_COST if earnings_in_window else 1.0) * (1 + cost_bump)
        return payoff / cost - 1, cost
    premium = formula * SELL_HAIRCUT * (1 - cost_bump)
    return (premium - payoff) / premium, premium


def _matches(frame, conditions):
    keep = np.ones(len(frame), dtype=bool)
    for feature, (op, value) in conditions.items():
        col = frame[feature].to_numpy(float)
        with np.errstate(invalid="ignore"):
            keep &= OPS[op](col, value) & ~np.isnan(col)     # a missing feature never matches
    return keep


def _earnings_between(report_dates, start, end):
    """True if a report date falls in (start, end]."""
    return any(start < d <= end for d in report_dates)


def run(panel, plan, horizon=None, cost_bump=0.0, conditions=None, exclude_earnings=False,
        exclude_tickers=(), random_rate=None, seed=0):
    """All trades for one configuration of plan v0. Returns (trades DataFrame, drop counts).

    conditions=None uses the plan's; {} is the no-condition baseline. random_rate draws setups at
    random with that probability instead of using conditions (random-selection baseline).
    exclude_earnings drops entries whose holding window contains an earnings date (F1); tickers
    without earnings coverage are left out and counted.
    """
    family = plan["family"]
    H = horizon_of(plan, horizon)
    conds = plan["conditions"] if conditions is None else conditions
    train_start = pd.Timestamp(STRADDLE_TRAIN_START if family in STRADDLES else TRAIN_START)
    train_end, valid_start, valid_end = pd.Timestamp(TRAIN_END), pd.Timestamp(VALID_START), pd.Timestamp(VALID_END)
    rng = np.random.default_rng(seed)
    drops = {"train_exit_in_2026": 0, "validation_exit_past_data": 0, "stale_iv": 0,
             "f1_no_earnings_coverage": 0, "earnings_unknown_cost": 0}
    rows = []
    for ticker, f in panel.frames.items():
        if ticker in exclude_tickers:
            continue
        reports = [pd.Timestamp(d) for d in panel.earnings.get(ticker) or []]
        if exclude_earnings and not reports:
            drops["f1_no_earnings_coverage"] += 1
            continue
        dates = f.index
        n = len(dates)
        in_train = (dates >= train_start) & (dates <= train_end)
        in_valid = (dates >= valid_start) & (dates <= valid_end)
        cand = np.flatnonzero(in_train | in_valid)
        if not len(cand):
            continue
        if random_rate is None:
            ok = _matches(f, conds)
        else:
            ok = rng.random(n) < random_rate
        o, h, l = (f[c].to_numpy(float) for c in ("Open", "High", "Low"))
        adj, close = f["Adj Close"].to_numpy(float), f["Close"].to_numpy(float)
        if family in STRADDLES:
            iv = f["iv"].to_numpy(float)
            stale = f["iv_stale"].to_numpy(bool)
            earn = f["earnings_within_10d"].to_numpy(float)
            iv_dates = f["iv_date"]
        last_exit = -1
        for i in cand:
            end_i = i + H
            if in_train[i] and (end_i >= n or dates[end_i] >= valid_start):
                drops["train_exit_in_2026"] += 1
                continue
            if in_valid[i] and end_i >= n:
                drops["validation_exit_past_data"] += 1
                continue
            if not ok[i] or i <= last_exit:
                continue
            if exclude_earnings and _earnings_between(reports, dates[i], dates[end_i]):
                continue
            split = "train" if in_train[i] else "validation"
            if family == "stock_long":
                ex = plan["exit"]
                entry = adj[i]
                j, price = stock_exit(o, h, l, adj, i, H, entry * (1 - ex["stop_pct"]), entry * (1 + ex["target_pct"]))
                rec = {"ret": price / entry - 1, "premium": np.nan, "payoff": np.nan, "earnings_in_window": np.nan}
            else:
                if stale[i] or math.isnan(iv[i]):
                    drops["stale_iv"] += 1
                    continue
                j = end_i
                payoff = abs(close[j] / close[i] - 1)
                e = earn[i]
                if math.isnan(e):
                    drops["earnings_unknown_cost"] += 1
                ret, prem = straddle_return(family, iv[i], payoff, e == 1, cost_bump)
                rec = {"ret": ret, "premium": prem, "payoff": payoff, "earnings_in_window": e,
                       "iv_date": iv_dates.iloc[i]}
            last_exit = j
            rows.append({"ticker": ticker, "date": dates[i], "exit_date": dates[j], "split": split, **rec})
    trades = pd.DataFrame(rows, columns=["ticker", "date", "exit_date", "split", "ret", "premium",
                                         "payoff", "earnings_in_window", "iv_date"])
    if len(trades):
        trades = trades.sort_values(["date", "ticker"]).reset_index(drop=True)
    assert_no_leakage(trades)
    return trades, drops


def assert_no_leakage(trades):
    """No train trade's outcome reaches 2026, no setup after the validation window, no implied vol
    from after the setup day. Raises LeakageError. Earnings features are exempt (spec section 3)."""
    if not len(trades):
        return
    train = trades[trades["split"] == "train"]
    if len(train) and (train["exit_date"] >= pd.Timestamp(VALID_START)).any():
        raise LeakageError("a train trade exits on or after %s" % VALID_START)
    if (trades["date"] > pd.Timestamp(VALID_END)).any():
        raise LeakageError("a setup is dated after the validation window (%s)" % VALID_END)
    if "iv_date" in trades and trades["iv_date"].notna().any():
        iv = trades.dropna(subset=["iv_date"])
        if (pd.to_datetime(iv["iv_date"]) > iv["date"]).any():
            raise LeakageError("implied vol dated after its setup day")
