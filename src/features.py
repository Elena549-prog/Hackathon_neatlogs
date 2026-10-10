"""Step 3: features for one setup day, using only prices at or before that day.

Every number here is computed from rows 0..t of the price table. Nothing after t is read,
so the model can never "see the future" through its inputs. tests/test_labels.py checks
this (the leakage test).
"""
import math

import numpy as np

RETURN_WINDOWS = (1, 5, 10, 20)
VOL_WINDOW = 20
MA_SHORT = 50
MA_LONG = 200

FEATURE_NAMES = (
    ["ret_%dd" % k for k in RETURN_WINDOWS]
    + ["vol_%dd" % VOL_WINDOW, "close_to_ma%d" % MA_SHORT, "close_to_ma%d" % MA_LONG]
)


def features_at(prices_df, t_index):
    """Features for row `t_index` of `prices_df`, from Adj Close rows 0..t_index only.

    - ret_Nd: Adj Close today / Adj Close N trading days ago - 1
    - vol_20d: standard deviation of the last 20 daily returns
    - close_to_maN: Adj Close today / average Adj Close of the last N days (today included)

    A feature that needs more history than exists is NaN. SPEC: setups with a NaN
    200-day ratio are dropped later.
    """
    adj = prices_df["Adj Close"].to_numpy(dtype=float)[: t_index + 1]  # the cut that prevents leakage
    today = adj[-1]
    n = len(adj)

    out = {}
    for k in RETURN_WINDOWS:
        out["ret_%dd" % k] = today / adj[-1 - k] - 1 if n > k else math.nan

    if n > VOL_WINDOW:
        daily = adj[-VOL_WINDOW:] / adj[-VOL_WINDOW - 1:-1] - 1
        out["vol_%dd" % VOL_WINDOW] = float(np.std(daily, ddof=1))
    else:
        out["vol_%dd" % VOL_WINDOW] = math.nan

    for w in (MA_SHORT, MA_LONG):
        out["close_to_ma%d" % w] = today / adj[-w:].mean() if n >= w else math.nan

    return {name: float(out[name]) for name in FEATURE_NAMES}
