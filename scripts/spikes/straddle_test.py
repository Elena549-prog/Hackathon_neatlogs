"""SPIKE (throwaway): do 10-trading-day at-the-money straddles have a predictable edge on 50 stocks?

Design fixed before running:
- Implied volatility: DoltHub post-no-preference/options, volatility_history.iv_current (free). A trade
  entered at day t's close uses the latest row dated on or before t.
- Straddle cost (share of price) = 0.7979 x IV x sqrt(10/252) (ATM approximation) x 1.05 (5% bid/ask haircut
  on entry). Payoff at day t+10 = |Close(t+10)/Close(t) - 1|. Return = payoff / cost - 1.
- Train: entries 2020-01-01..2025-12-31 whose exit is before 2026. Validation: entries 2026-01-01..2026-06-30.
  The test split is not touched (no implied volatility is fetched after 2026-06-30).
- Q1: mean return of buying every straddle. Q2: can a model trained on train pick profitable ones in validation?
"""
import json
import os
import sys
import time
import urllib.parse
import urllib.request

import numpy as np
import pandas as pd
import yfinance as yf

sys.path.insert(0, "."); sys.path.insert(0, os.path.dirname(__file__))
from signal_test_50_cfg import TICKERS
from src.baselines import block_bootstrap, models, scores
from src.features import FEATURE_NAMES, features_at

API = "https://www.dolthub.com/api/v1alpha1/post-no-preference/options/master?q="
HOLD, HAIRCUT = 10, 1.05
TRAIN, VALID = ("2020-01-01", "2025-12-31"), ("2026-01-01", "2026-06-30")
CACHE = os.path.join(os.path.dirname(__file__), "iv_50.csv")


def q(sql):
    for attempt in range(4):
        try:
            with urllib.request.urlopen(API + urllib.parse.quote(sql), timeout=60) as r:
                d = json.load(r)
            if d["query_execution_status"] in ("Success", "RowLimit"):
                return d["rows"]
        except Exception:
            pass
        time.sleep(2 * (attempt + 1))
    raise RuntimeError("query failed: " + sql[:120])


if os.path.exists(CACHE):
    iv = pd.read_csv(CACHE, parse_dates=["date"])
else:
    from concurrent.futures import ThreadPoolExecutor
    syms = ",".join("'%s'" % t.replace("-", ".") for t in TICKERS)
    starts = pd.date_range("2019-06-01", VALID[1], freq="14D")       # the table is keyed by date: query date windows

    def chunk(a):
        b = min(a + pd.Timedelta(days=13), pd.Timestamp(VALID[1]))
        rows = q("SELECT date, act_symbol, iv_current, hv_current FROM volatility_history WHERE date BETWEEN '%s' "
                 "AND '%s' AND act_symbol IN (%s)" % (a.date(), b.date(), syms))
        if len(rows) >= 1000:
            raise RuntimeError("row limit hit for %s..%s" % (a.date(), b.date()))
        return rows

    with ThreadPoolExecutor(4) as pool:
        parts = [r for rows in pool.map(chunk, starts) for r in rows]
    iv = pd.DataFrame(parts)
    iv["ticker"] = iv.pop("act_symbol").str.replace(".", "-", regex=False)
    iv["date"] = pd.to_datetime(iv["date"])
    for c in ("iv_current", "hv_current"):
        iv[c] = pd.to_numeric(iv[c], errors="coerce")
    iv.to_csv(CACHE, index=False)
print("implied-vol rows: %d for %d tickers, %s..%s" % (len(iv), iv.ticker.nunique(), iv.date.min().date(), iv.date.max().date()))

raw = yf.download(TICKERS + ["SPY", "^VIX"], start="2019-01-01", end="2026-07-31", auto_adjust=False,
                  progress=False, group_by="ticker")
vix = raw["^VIX"]["Adj Close"].dropna()
spy = raw["SPY"]["Adj Close"].dropna()

rows = []
for t in TICKERS:
    df = raw[t][["Open", "High", "Low", "Close", "Adj Close", "Volume"]].dropna()
    close = df["Close"].to_numpy(float)            # split-adjusted, not dividend-adjusted: what options settle on
    tiv = iv[iv.ticker == t].dropna(subset=["iv_current"]).set_index("date").sort_index()
    for i, d in enumerate(df.index):
        if i < 200 or i + HOLD >= len(df):
            continue
        if pd.Timestamp(TRAIN[0]) <= d <= pd.Timestamp(TRAIN[1]):
            if df.index[i + HOLD] >= pd.Timestamp(VALID[0]):
                continue
            split = "train"
        elif pd.Timestamp(VALID[0]) <= d <= pd.Timestamp(VALID[1]):
            split = "validation"
        else:
            continue
        known = tiv.loc[:d]
        if known.empty or (d - known.index[-1]).days > 5:
            continue                                # no fresh implied vol for this day
        ivc, hvc = known["iv_current"].iloc[-1], known["hv_current"].iloc[-1]
        cost = 0.7979 * ivc * np.sqrt(HOLD / 252) * HAIRCUT
        payoff = abs(close[i + HOLD] / close[i] - 1)
        f = features_at(df, i)
        v = vix.loc[:d]
        s = spy.loc[:d]
        rows.append({"ticker": t, "date": d, "split": split, "ret": payoff / cost - 1, "y": int(payoff > cost),
                     "iv": ivc, "hv": hvc, "iv_hv_ratio": ivc / hvc if hvc else np.nan,
                     "iv_minus_rv20": ivc - f["vol_20d"] * np.sqrt(252),
                     "vix": v.iloc[-1], "vix_chg_5d": v.iloc[-1] / v.iloc[-6] - 1,
                     "spy_ret_20d": s.iloc[-1] / s.iloc[-21] - 1, "cost": cost, **f})
X = pd.DataFrame(rows).dropna()
X.to_csv(os.path.join(os.path.dirname(__file__), "straddles_50.csv"), index=False)

print("\nQ1: buy every straddle (approximate cost incl. 5% haircut)")
for s in ("train", "validation"):
    p = X[X.split == s]
    print("  %-10s trades %6d | mean return %+.1f%% | median %+.1f%% | win rate %.1f%% | mean cost %.2f%% of price"
          % (s, len(p), 100 * p.ret.mean(), 100 * p.ret.median(), 100 * p.y.mean(), 100 * p.cost.mean()))

cols = ["iv", "hv", "iv_hv_ratio", "iv_minus_rv20", "vix", "vix_chg_5d", "spy_ret_20d"] + list(FEATURE_NAMES)
tr, va = X[X.split == "train"], X[X.split == "validation"]
print("\nQ2: pick straddles (train %d, validation %d)" % (len(tr), len(va)))
preds = {}
for name, m in models().items():
    if name == "Base rate":
        continue
    m.fit(tr[cols], tr.y)
    preds[name] = m.predict_proba(va[cols])[:, 1]
ci = block_bootstrap(va.date.dt.strftime("%Y-%m-%d"), va.y.to_numpy(), preds)
rng = np.random.default_rng(0)
for name, p in preds.items():
    order = np.argsort(-p)
    top = va.iloc[order[: len(va) // 10]]
    dates = top.date.unique()
    boot = []
    for _ in range(2000):                           # bootstrap over entry dates for the top-decile mean return
        pick = rng.choice(dates, len(dates))
        boot.append(pd.concat([top[top.date == d] for d in pick[:60]]).ret.mean())
    print("  %-20s AUC %.3f (90%% CI %.3f-%.3f) | top 10%% picks: mean return %+.1f%% (rough 90%% CI %+.1f%% to %+.1f%%), win rate %.1f%%"
          % (name, scores(va.y.to_numpy(), p)["auc"], *ci[name]["auc"], 100 * top.ret.mean(),
             100 * np.percentile(boot, 5), 100 * np.percentile(boot, 95), 100 * top.y.mean()))
