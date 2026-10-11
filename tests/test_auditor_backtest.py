"""Backtest trade rules (AUDITOR_SPEC section 2) on hand-made price paths."""
import numpy as np
import pandas as pd
import pytest

from src.auditor import backtest as bt
from src.auditor import data

N = 260


def frame(start="2025-06-02", n=N, close=100.0, adj_factor=1.0):
    dates = pd.bdate_range(start, periods=n)
    c = np.full(n, close, dtype=float)
    return pd.DataFrame({"Open": c, "High": c, "Low": c, "Close": c, "Adj Close": c * adj_factor,
                         "Volume": np.full(n, 1e6)}, index=dates)


def world(df, **others):
    """Features for one ticker (plus a market), with a 'flag' column that marks the entry days."""
    prices = {"AAA": df, **others}
    mkt = {"SPY": frame(n=len(df), start=df.index[0]), "^VIX": frame(n=len(df), start=df.index[0], close=20)}
    feats = data.build_features(prices, mkt, None, {})
    feats["flag"] = 0.0
    return prices, feats


def plan(**over):
    p = {"refused": False, "family": "stock_long", "universe_group": "all_50", "conditions": {"flag": [">", 0.5]},
         "exit": {"target_pct": 0.05, "stop_pct": 0.03, "horizon_days": 10}}
    p.update(over)
    return p


def entry_at(feats, df, i):
    """Mark price row i of df as an entry day in the feature frame."""
    feats.loc[feats.date == df.index[i], "flag"] = 1.0
    return df.index[i]


def set_bar(df, i, **cols):
    for k, v in cols.items():
        df.iloc[i, df.columns.get_loc(k)] = v


def run(prices, feats, p, split="train", **kw):
    return bt.run_backtest(prices, feats, p, {}, split, **kw)


# All frames below start 2025-06-02; row 199 is the first feature row; entries at row 200 (2026-03-10? no: 2025-06-02
# + 200 bdays = 2026-03-09) fall in the validation window, so tests use split="validation" unless stated.

def test_first_hit_target():
    df = frame()
    prices, feats = world(df)
    d = entry_at(feats, df, 200)
    set_bar(df, 203, High=106.0)
    trades, drops = run(prices, feats, plan(), "validation")
    assert len(trades) == 1 and abs(trades.ret.iloc[0] - 0.05) < 1e-12 and trades.exit_date.iloc[0] == df.index[203]


def test_first_hit_stop_and_same_day_double_hit_is_a_loss():
    df = frame()
    prices, feats = world(df)
    entry_at(feats, df, 200)
    set_bar(df, 202, High=106.0, Low=96.0)
    trades, _ = run(prices, feats, plan(), "validation")
    assert abs(trades.ret.iloc[0] + 0.03) < 1e-12


def test_gap_down_fills_at_open():
    df = frame()
    prices, feats = world(df)
    entry_at(feats, df, 200)
    set_bar(df, 201, Open=95.0, High=95.5, Low=94.0)
    trades, _ = run(prices, feats, plan(), "validation")
    assert abs(trades.ret.iloc[0] + 0.05) < 1e-12          # exit at the Open (95), not the stop (97)


def test_gap_up_fills_at_open():
    df = frame()
    prices, feats = world(df)
    entry_at(feats, df, 200)
    set_bar(df, 201, Open=108.0, High=109.0, Low=107.0)
    trades, _ = run(prices, feats, plan(), "validation")
    assert abs(trades.ret.iloc[0] - 0.08) < 1e-12


def test_horizon_exit_at_close():
    df = frame()
    prices, feats = world(df)
    entry_at(feats, df, 200)
    set_bar(df, 210, Close=101.0, **{"Adj Close": 101.0})
    trades, _ = run(prices, feats, plan(), "validation")
    assert abs(trades.ret.iloc[0] - 0.01) < 1e-12 and trades.exit_date.iloc[0] == df.index[210]


def test_adjusted_scale():
    df = frame(adj_factor=0.5)                                # Adj Close = 50, raw Close = 100
    prices, feats = world(df)
    entry_at(feats, df, 200)
    set_bar(df, 204, High=106.0)                               # raw +6% -> scaled high 53 >= target 52.5
    trades, _ = run(prices, feats, plan(), "validation")
    assert abs(trades.entry.iloc[0] - 50.0) < 1e-12 and abs(trades.ret.iloc[0] - 0.05) < 1e-12


def test_one_open_trade_per_ticker():
    df = frame()
    prices, feats = world(df)
    entry_at(feats, df, 200)
    entry_at(feats, df, 203)
    entry_at(feats, df, 215)
    trades, _ = run(prices, feats, plan(), "validation")
    assert list(trades.entry_date) == [df.index[200], df.index[215]]


def test_train_exit_after_cutoff_dropped():
    df = frame(start="2025-01-02", n=300)                     # row 199 = 2025-10-09 ... row 250 = 2025-12-19
    prices, feats = world(df)
    i_late = int(np.where(df.index >= pd.Timestamp("2025-12-22"))[0][0])
    entry_at(feats, df, i_late)                                    # exit 10 trading days later lands in 2026
    i_ok = 220
    entry_at(feats, df, i_ok)
    trades, drops = run(prices, feats, plan(), "train")
    assert list(trades.entry_date) == [df.index[i_ok]] and drops["exit_after_cutoff"] == 1


def test_validation_exit_past_data_dropped():
    df = frame()
    prices, feats = world(df)
    entry_at(feats, df, len(df) - 5)                               # fewer than 10 rows left
    trades, drops = run(prices, feats, plan(), "validation")
    assert len(trades) == 0 and drops["exit_past_data"] == 1


def iv_frame(df, iv=0.30, hv=0.20):
    return pd.DataFrame({"date": df.index, "ticker": "AAA", "iv_current": iv, "hv_current": hv})


def straddle_world(df, iv=0.30, earnings=None):
    prices = {"AAA": df}
    mkt = {"SPY": frame(n=len(df), start=df.index[0]), "^VIX": frame(n=len(df), start=df.index[0], close=20)}
    feats = data.build_features(prices, mkt, iv_frame(df, iv), earnings or {})
    feats["flag"] = 0.0
    return prices, feats


def test_straddle_buy_return_and_cost():
    df = frame()
    set_bar(df, 210, Close=104.0, **{"Adj Close": 104.0})
    prices, feats = straddle_world(df)
    entry_at(feats, df, 200)
    trades, drops = bt.run_backtest(prices, feats, plan(family="straddle_buy"), {}, "validation")
    cost = 0.7979 * 0.30 * np.sqrt(10 / 252) * 1.05
    assert abs(trades.cost.iloc[0] - cost) < 1e-12 and abs(trades.ret.iloc[0] - (0.04 / cost - 1)) < 1e-9
    assert drops["earnings_in_window"] == 0


def test_straddle_earnings_factor_and_sell_return():
    df = frame()
    set_bar(df, 210, Close=104.0, **{"Adj Close": 104.0})
    earnings = {"AAA": [df.index[205]]}
    prices, feats = straddle_world(df, earnings=earnings)
    entry_at(feats, df, 200)
    buy, drops = bt.run_backtest(prices, feats, plan(family="straddle_buy"), earnings, "validation")
    assert abs(buy.cost.iloc[0] - 0.7979 * 0.30 * np.sqrt(10 / 252) * 1.05 * 1.20) < 1e-12 and drops["earnings_in_window"] == 1
    sell, _ = bt.run_backtest(prices, feats, plan(family="straddle_sell"), earnings, "validation")
    premium = 0.7979 * 0.30 * np.sqrt(10 / 252) * 0.95
    assert abs(sell.premium.iloc[0] - premium) < 1e-12 and abs(sell.ret.iloc[0] - (premium - 0.04) / premium) < 1e-9


def test_stale_iv_skipped():
    df = frame()
    prices, feats = straddle_world(df)
    feats.loc[feats.index[feats.date == df.index[200]], "iv"] = np.nan   # the merge left no fresh IV that day
    entry_at(feats, df, 200)
    trades, drops = bt.run_backtest(prices, feats, plan(family="straddle_buy"), {}, "validation")
    assert len(trades) == 0 and drops["stale_iv"] == 1


def test_stricter_cost():
    df = frame()
    set_bar(df, 210, Close=104.0, **{"Adj Close": 104.0})
    prices, feats = straddle_world(df)
    entry_at(feats, df, 200)
    buy, _ = bt.run_backtest(prices, feats, plan(family="straddle_buy"), {}, "validation", stricter=True)
    assert abs(buy.cost.iloc[0] - 0.7979 * 0.30 * np.sqrt(10 / 252) * 1.05 * 1.10) < 1e-12
    sell, _ = bt.run_backtest(prices, feats, plan(family="straddle_sell"), {}, "validation", stricter=True)
    assert abs(sell.premium.iloc[0] - 0.7979 * 0.30 * np.sqrt(10 / 252) * 0.95 * 0.90) < 1e-12


def test_straddle_train_starts_2020():
    df = frame(start="2019-01-02", n=600)
    prices, feats = straddle_world(df)
    i_2019 = int(np.where(df.index >= pd.Timestamp("2019-11-01"))[0][0])
    i_2020 = int(np.where(df.index >= pd.Timestamp("2020-03-02"))[0][0])
    entry_at(feats, df, i_2019)
    entry_at(feats, df, i_2020)
    trades, _ = bt.run_backtest(prices, feats, plan(family="straddle_buy"), {}, "train")
    assert list(trades.entry_date) == [df.index[i_2020]]


def test_select_setups_ignores_nan_feature_rows():
    df = frame()
    prices, feats = world(df)
    entry_at(feats, df, 200)
    feats.loc[feats.index[feats.date == df.index[200]], "ret_5d"] = np.nan
    setups = bt.select_setups(feats, plan(conditions={"flag": [">", 0.5], "ret_5d": ["<", 1.0]}), "validation")
    assert len(setups) == 0
