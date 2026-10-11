"""Backtest rules, features and leakage (spec sections 2, 3, 6, 12)."""
import math

import numpy as np
import pandas as pd
import pytest

from src.auditor import backtest
from src.auditor.data import LeakageError, Panel, earnings_features, iv_features, price_features
from src.features import FEATURE_NAMES, features_at
from tests.auditor_helpers import make_panel_frame


# --------------------------------------------------------------------------------- stock exits

def exit_of(opens, highs, lows, closes, horizon=10, stop=97.0, target=105.0):
    return backtest.stock_exit(np.array(opens, float), np.array(highs, float), np.array(lows, float),
                               np.array(closes, float), 0, horizon, stop, target)


def test_first_hit_target():
    assert exit_of([100, 101, 102], [100, 103, 106], [100, 99, 101], [100, 102, 104]) == (2, 105.0)


def test_first_hit_stop():
    assert exit_of([100, 99, 98], [100, 101, 110], [100, 96, 95], [100, 98, 100]) == (1, 97.0)


def test_both_hit_same_day_is_stop():
    assert exit_of([100, 100], [100, 106], [100, 96], [100, 100]) == (1, 97.0)


def test_gap_below_stop_fills_at_the_open():
    assert exit_of([100, 95], [100, 96], [100, 94], [100, 95]) == (1, 95.0)


def test_gap_above_target_fills_at_the_open():
    assert exit_of([100, 108], [100, 109], [100, 107], [100, 108]) == (1, 108.0)


def test_no_hit_exits_at_the_horizon_close():
    closes = [100, 101, 102, 101, 103]
    assert exit_of(closes, closes, closes, closes, horizon=4) == (4, 103.0)


# ------------------------------------------------------------------------- trades and splits

def stock_plan(conditions=None, horizon=3):
    return {"family": "stock_long", "conditions": conditions or {},
            "exit": {"target_pct": 0.05, "stop_pct": 0.03, "horizon_days": horizon}}


def panel_of(frames, earnings=None):
    cal = sorted(set().union(*[f.index for f in frames.values()]))
    return Panel(frames, pd.DatetimeIndex(cal), earnings or {t: [] for t in frames})


def test_one_open_trade_per_ticker():
    f = make_panel_frame([100] * 40, start="2026-01-01")      # flat: every trade runs to the horizon
    trades, _ = backtest.run(panel_of({"X": f}), stock_plan(horizon=3))
    idx = [f.index.get_loc(d) for d in trades["date"]]
    assert idx[:3] == [0, 4, 8]                                # entry only after the previous exit day
    assert (trades["ret"] == 0).all()


def test_train_setups_whose_horizon_reaches_2026_are_dropped():
    f = make_panel_frame([100] * 30, start="2025-12-15")
    trades, drops = backtest.run(panel_of({"X": f}), stock_plan(horizon=5))
    train = trades[trades["split"] == "train"]
    assert (train["exit_date"] < pd.Timestamp("2026-01-01")).all()
    assert drops["train_exit_in_2026"] > 0


def test_validation_setups_past_the_data_are_dropped():
    f = make_panel_frame([100] * 10, start="2026-06-22")
    trades, drops = backtest.run(panel_of({"X": f}), stock_plan(horizon=5))
    assert drops["validation_exit_past_data"] > 0
    assert (trades["date"] <= pd.Timestamp("2026-06-30")).all()


def test_missing_feature_never_matches():
    f = make_panel_frame([100] * 20, start="2026-01-01", extra={"ret_5d": np.nan})
    trades, _ = backtest.run(panel_of({"X": f}), stock_plan({"ret_5d": ["<", 1.0]}))
    assert len(trades) == 0


# ------------------------------------------------------------------------------- straddles

def straddle_frame(closes, iv=0.25, stale=False, earn=0.0):
    n = len(closes)
    f = make_panel_frame(closes, start="2026-01-01")
    f["iv"] = iv
    f["iv_stale"] = stale
    f["iv_date"] = f.index
    f["earnings_within_10d"] = earn
    return f


def test_straddle_payoff_and_cost_hand_example():
    closes = [100] * 10 + [110] + [110] * 10
    f = straddle_frame(closes)
    buy, _ = backtest.run(panel_of({"X": f}), {"family": "straddle_buy", "conditions": {}})
    formula = 0.7979 * 0.25 * math.sqrt(10 / 252)
    first = buy.iloc[0]
    assert first["payoff"] == pytest.approx(0.10)
    assert first["premium"] == pytest.approx(formula * 1.05)
    assert first["ret"] == pytest.approx(0.10 / (formula * 1.05) - 1)
    sell, _ = backtest.run(panel_of({"X": f}), {"family": "straddle_sell", "conditions": {}})
    prem = formula * 0.95
    assert sell.iloc[0]["ret"] == pytest.approx((prem - 0.10) / prem)


def test_straddle_buyer_pays_1_20_with_earnings_in_window():
    f = straddle_frame([100] * 21, earn=1.0)
    t, _ = backtest.run(panel_of({"X": f}), {"family": "straddle_buy", "conditions": {}})
    assert t.iloc[0]["premium"] == pytest.approx(0.7979 * 0.25 * math.sqrt(10 / 252) * 1.05 * 1.20)


def test_stricter_cost_bump():
    r_plain, c_plain = backtest.straddle_return("straddle_buy", 0.25, 0.05, False)
    r_strict, c_strict = backtest.straddle_return("straddle_buy", 0.25, 0.05, False, cost_bump=0.10)
    assert c_strict == pytest.approx(c_plain * 1.10) and r_strict < r_plain
    _, p_plain = backtest.straddle_return("straddle_sell", 0.25, 0.05, False)
    _, p_strict = backtest.straddle_return("straddle_sell", 0.25, 0.05, False, cost_bump=0.10)
    assert p_strict == pytest.approx(p_plain * 0.90)


def test_stale_implied_vol_skips_and_counts():
    f = straddle_frame([100] * 21, stale=True)
    t, drops = backtest.run(panel_of({"X": f}), {"family": "straddle_buy", "conditions": {}})
    assert len(t) == 0 and drops["stale_iv"] > 0


def test_iv_features_mark_rows_older_than_5_days_stale():
    dates = pd.bdate_range("2026-01-05", periods=10)
    rows = pd.DataFrame({"date": pd.to_datetime(["2026-01-05"]), "iv_current": [0.3], "hv_current": [0.2]})
    f = iv_features(dates, rows, np.full(10, 0.01))
    assert f["iv"].iloc[0] == 0.3 and not f["iv_stale"].iloc[0]
    assert f["iv_stale"].iloc[-1] and np.isnan(f["iv"].iloc[-1])      # 2026-01-16: 11 days old
    assert f["iv_hv_ratio"].iloc[0] == pytest.approx(1.5)
    assert f["iv_minus_rv20"].iloc[0] == pytest.approx(0.3 - 0.01 * math.sqrt(252))


# -------------------------------------------------------------------------- features, leakage

def test_vectorized_price_features_equal_src_features():
    rng = np.random.default_rng(1)
    close = 100 * np.cumprod(1 + rng.normal(0, 0.02, 260))
    df = pd.DataFrame({"Adj Close": close, "Close": close, "Volume": rng.integers(1, 9, 260).astype(float)},
                      index=pd.bdate_range("2024-01-01", periods=260))
    vec = price_features(df)
    for i in (0, 25, 60, 220, 259):
        ref = features_at(df, i)
        for k in FEATURE_NAMES:
            a, b = vec[k].iloc[i], ref[k]
            assert (math.isnan(a) and math.isnan(b)) or a == pytest.approx(b), (i, k)


def test_volume_ratios_use_previous_days_only():
    df = pd.DataFrame({"Adj Close": np.ones(30), "Close": np.ones(30), "Volume": [1.0] * 25 + [10.0] * 5},
                      index=pd.bdate_range("2024-01-01", periods=30))
    v = price_features(df)
    assert v["vol_ratio_5d"].iloc[25] == pytest.approx(10.0)       # previous five days were 1


def test_earnings_features():
    dates = pd.bdate_range("2026-01-05", periods=30)
    f = earnings_features(dates, ["2026-01-06", "2026-01-26"])
    assert np.isnan(f["earnings_within_10d"].iloc[0])                 # before the earliest known date
    assert f["earnings_within_10d"].iloc[1] == 0      # 01-06: next report 01-26 is 14 trading days ahead
    assert f["earnings_within_10d"].iloc[5] == 1      # 01-12: 01-26 is exactly 10 trading days ahead
    assert f["earnings_within_10d"].iloc[4] == 0      # 01-09: 11 trading days ahead
    assert f["days_since_earnings"].iloc[3] == 2      # 01-08: two trading days after 01-06
    no_cov = earnings_features(dates, [])
    assert no_cov.isna().all().all()


def test_leakage_assertion_raises():
    bad_train = pd.DataFrame({"ticker": ["X"], "date": [pd.Timestamp("2025-12-20")],
                              "exit_date": [pd.Timestamp("2026-01-05")], "split": ["train"], "ret": [0.0],
                              "iv_date": [pd.NaT]})
    with pytest.raises(LeakageError):
        backtest.assert_no_leakage(bad_train)
    future_iv = pd.DataFrame({"ticker": ["X"], "date": [pd.Timestamp("2026-02-02")],
                              "exit_date": [pd.Timestamp("2026-02-16")], "split": ["validation"], "ret": [0.0],
                              "iv_date": [pd.Timestamp("2026-02-03")]})
    with pytest.raises(LeakageError):
        backtest.assert_no_leakage(future_iv)
    after_window = future_iv.assign(date=pd.Timestamp("2026-07-01"), iv_date=pd.NaT)
    with pytest.raises(LeakageError):
        backtest.assert_no_leakage(after_window)
