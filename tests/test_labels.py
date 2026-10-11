"""Step 3 tests: the label rule on hand-built price paths, the setup table, and the leakage test."""
import math

import numpy as np
import pandas as pd
import pytest

from src.features import FEATURE_NAMES, features_at
from src.labels import HORIZON, adjusted_high_low, label_setup, make_setups, split_for


def flat_prices(n=30, price=100.0):
    """A price that never moves: High = Low = Close = Adj Close = 100 every day."""
    dates = pd.bdate_range("2025-01-01", periods=n, name="Date")
    return pd.DataFrame({"Open": price, "High": price, "Low": price, "Close": price,
                         "Adj Close": price, "Volume": 1}, index=dates)


def set_day(df, i, high=None, low=None):
    if high is not None:
        df.iloc[i, df.columns.get_loc("High")] = high
    if low is not None:
        df.iloc[i, df.columns.get_loc("Low")] = low


# ------------------------------------------------------------------------- the label rule
# Entry is the Adj Close on day t = 0, i.e. 100. Target 105, stop 97.

def test_win_path_hits_target_first():
    df = flat_prices()
    set_day(df, 3, high=105.0)           # +5% on day 3
    set_day(df, 6, low=96.0)             # -3% later doesn't matter
    assert label_setup(df, 0) == 1


def test_loss_path_hits_stop_first():
    df = flat_prices()
    set_day(df, 2, low=97.0)             # -3% on day 2
    set_day(df, 5, high=110.0)
    assert label_setup(df, 0) == 0


def test_both_on_same_day_counts_as_loss():
    df = flat_prices()
    set_day(df, 4, high=106.0, low=96.0)
    assert label_setup(df, 0) == 0


def test_neither_hit_is_dropped():
    df = flat_prices()
    set_day(df, 5, high=104.9, low=97.1)  # close, but no hit
    assert label_setup(df, 0) is None


def test_hit_after_day_10_is_ignored():
    df = flat_prices()
    set_day(df, HORIZON + 1, high=120.0)  # day 11 is outside the window
    assert label_setup(df, 0) is None


def test_day_t_itself_is_not_checked():
    df = flat_prices()
    set_day(df, 0, high=120.0)            # the setup day's own high is not "after" t
    assert label_setup(df, 0) is None


def test_high_low_use_the_adjusted_scale():
    df = flat_prices()
    df["Adj Close"] = 98.0                # adjusted is 2% below raw every day
    set_day(df, 3, high=103.0)            # raw high is 5.1% above the adjusted entry of 98...
    # ...but on the adjusted scale it is 103 * 98/100 = 100.94, only +3%: no hit.
    assert label_setup(df, 0) is None
    high, _ = adjusted_high_low(df)
    assert high.iloc[3] == pytest.approx(100.94)


# ----------------------------------------------------------------------- the setup table

def test_near_end_setups_are_not_in_the_table():
    df = flat_prices(n=30)
    setups = make_setups(df, "TEST")
    assert len(setups) == 30 - HORIZON
    assert setups["date"].iloc[-1] == df.index[30 - HORIZON - 1]   # last t with t+10 present
    with pytest.raises(ValueError):
        label_setup(df, 30 - HORIZON)                              # first t without t+10


def test_split_boundaries():
    assert split_for(pd.Timestamp("2025-12-31")) == "train"
    assert split_for(pd.Timestamp("2026-01-01")) == "validation"
    assert split_for(pd.Timestamp("2026-06-30")) == "validation"
    assert split_for(pd.Timestamp("2026-07-01")) == "test"
    assert split_for(pd.Timestamp("2026-09-15")) == "test"
    assert split_for(pd.Timestamp("2026-09-16")) is None


# ---------------------------------------------------------------------------- features

def random_walk(n=260, seed=0):
    rng = np.random.default_rng(seed)
    close = 100 * np.cumprod(1 + rng.normal(0, 0.02, n))
    dates = pd.bdate_range("2024-01-01", periods=n, name="Date")
    return pd.DataFrame({"Open": close, "High": close * 1.01, "Low": close * 0.99,
                         "Close": close, "Adj Close": close, "Volume": 1}, index=dates)


def test_feature_values_by_hand():
    df = random_walk()
    t = 220
    adj = df["Adj Close"].to_numpy()
    f = features_at(df, t)
    assert f["ret_1d"] == pytest.approx(adj[t] / adj[t - 1] - 1)
    assert f["ret_20d"] == pytest.approx(adj[t] / adj[t - 20] - 1)
    daily = adj[t - 19:t + 1] / adj[t - 20:t] - 1
    assert f["vol_20d"] == pytest.approx(np.std(daily, ddof=1))
    assert f["close_to_ma50"] == pytest.approx(adj[t] / adj[t - 49:t + 1].mean())
    assert f["close_to_ma200"] == pytest.approx(adj[t] / adj[t - 199:t + 1].mean())


def test_ma200_is_nan_before_200_days():
    df = random_walk()
    assert math.isnan(features_at(df, 198)["close_to_ma200"])   # 199 days of history
    assert not math.isnan(features_at(df, 199)["close_to_ma200"])  # 200 days


@pytest.mark.parametrize("t", [0, 5, 49, 199, 220, 249])
def test_no_leakage_features_ignore_the_future(t):
    """Leakage test: features on the full series equal features on the series cut at t."""
    df = random_walk()
    full = features_at(df, t)
    cut = features_at(df.iloc[: t + 1], t)
    for name in FEATURE_NAMES:
        assert (math.isnan(full[name]) and math.isnan(cut[name])) or full[name] == cut[name], name
