"""SPIKE (throwaway): do market, earnings, or volume features add validation signal over the 7 price features?

Train on train, score on validation, same models and block bootstrap as src/baselines.py.
Feature groups were fixed before running. The test split is not touched.
"""
import sys

import numpy as np
import pandas as pd
import yfinance as yf

sys.path.insert(0, ".")
from src.baselines import block_bootstrap, models, scores
from src.data import TICKERS, load_prices
from src.features import FEATURE_NAMES
from src.labels import SETUPS_PATH

setups = pd.read_csv(SETUPS_PATH, parse_dates=["date"])
setups = setups[setups.split.isin(["train", "validation"])].reset_index(drop=True)

# ---- market: S&P 500 (SPY) and VIX, values at or before each setup day
mk = yf.download(["SPY", "^VIX"], start="2023-06-01", end="2026-10-01", auto_adjust=False, progress=False)["Adj Close"]
spy, vix = mk["SPY"].dropna(), mk["^VIX"].dropna()
spy_f = pd.DataFrame({
    "spy_ret_5d": spy / spy.shift(5) - 1,
    "spy_ret_20d": spy / spy.shift(20) - 1,
    "spy_close_to_ma50": spy / spy.rolling(50).mean(),
    "vix_level": vix.reindex(spy.index).ffill(),
    "vix_chg_5d": (vix / vix.shift(5) - 1).reindex(spy.index).ffill(),
})
spy_f.index = spy_f.index.tz_localize(None).normalize()

# ---- earnings: last report strictly before the setup date (most are after the close)
earn = {}
for t in TICKERS:
    e = yf.Ticker(t).get_earnings_dates(limit=24)
    e = e[e["Reported EPS"].notna()].copy()
    e.index = e.index.tz_convert("America/New_York").tz_localize(None).normalize()
    earn[t] = e.sort_index()

# ---- volume from the stored prices
vol = {t: load_prices(t)["Volume"] for t in TICKERS}

rows = []
for r in setups.itertuples():
    d = r.date
    out = {}
    m = spy_f.loc[:d].iloc[-1]
    out.update(m.to_dict())
    out["rel_ret_20d"] = r.ret_20d - m["spy_ret_20d"]
    e = earn[r.ticker]
    past = e[e.index < d]
    if len(past):
        last = past.index[-1]
        px = vol[r.ticker].index
        out["days_since_earnings"] = int(((px > last) & (px <= d)).sum())
        out["last_surprise_pct"] = float(np.clip(past["Surprise(%)"].iloc[-1], -50, 50))
    else:
        out["days_since_earnings"], out["last_surprise_pct"] = np.nan, np.nan
    v = vol[r.ticker].loc[:d]
    out["vol_ratio_20d"] = v.iloc[-1] / v.iloc[-21:-1].mean()
    out["vol_ratio_5d"] = v.iloc[-1] / v.iloc[-6:-1].mean()
    rows.append(out)
X = pd.concat([setups, pd.DataFrame(rows)], axis=1)

GROUPS = {
    "market": ["spy_ret_5d", "spy_ret_20d", "spy_close_to_ma50", "vix_level", "vix_chg_5d", "rel_ret_20d"],
    "earnings": ["days_since_earnings", "last_surprise_pct"],
    "volume": ["vol_ratio_20d", "vol_ratio_5d"],
}
SETS = {"price only (7)": list(FEATURE_NAMES)}
for g, cols in GROUPS.items():
    SETS["price + " + g] = list(FEATURE_NAMES) + cols
SETS["price + all (primary)"] = list(FEATURE_NAMES) + sum(GROUPS.values(), [])

print("missing values:", int(X[sum(GROUPS.values(), [])].isna().sum().sum()), "| setups:", X.split.value_counts().to_dict())
tr, va = X[X.split == "train"], X[X.split == "validation"]
y_tr, y_va = tr.label.to_numpy(), va.label.to_numpy()
print("\n| Features | Model | Validation AUC | 90% interval |")
print("|---|---|---|---|")
for name, cols in SETS.items():
    preds = {}
    for mname, model in models().items():
        if mname == "Base rate":
            continue
        model.fit(tr[cols].fillna(tr[cols].median()), y_tr)
        preds[mname] = model.predict_proba(va[cols].fillna(tr[cols].median()))[:, 1]
    ci = block_bootstrap(va.date.dt.strftime("%Y-%m-%d"), y_va, preds)
    for mname, p in preds.items():
        lo, hi = ci[mname]["auc"]
        print("| %s | %s | %.3f | %.3f-%.3f |" % (name, mname, scores(y_va, p)["auc"], lo, hi))
X.to_csv(sys.argv[1], index=False)
