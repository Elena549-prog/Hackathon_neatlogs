"""SPIKE (throwaway): with 50 stocks and train back to 2015, is there validation signal for the +5%/-3% bet?

Design fixed before running:
- Universe: the 50 tickers below (today's large caps: survivorship bias, fine for a signal test).
- Train setups 2015-01-01..2025-12-31; validation 2026-01-01..2026-06-30 (same window as the project).
  Train setups whose 10-day outcome ends in 2026 are dropped, so train labels never use validation prices.
- Label: src.labels.label_setup (+5% before -3% within 10 days, adjusted High/Low). Features: src.features.
- Models and block bootstrap: src.baselines. Primary: gradient boosting, price + market features.
- The test split (2026-07-01..) is not touched.
"""
import sys
import time

import numpy as np
import pandas as pd
import yfinance as yf

sys.path.insert(0, ".")
from src.baselines import block_bootstrap, models, scores
from src.features import FEATURE_NAMES, features_at
from src.labels import HORIZON, adjusted_high_low, label_setup

TICKERS = ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "BRK-B", "JPM", "V",
           "JNJ", "UNH", "XOM", "PG", "MA", "HD", "CVX", "MRK", "ABBV", "PEP",
           "KO", "AVGO", "COST", "LLY", "WMT", "BAC", "PFE", "TMO", "CSCO", "MCD",
           "ABT", "CRM", "DIS", "ACN", "ADBE", "NFLX", "WFC", "TXN", "NKE", "AMD",
           "INTC", "QCOM", "HON", "UNP", "IBM", "CAT", "GS", "BA", "AMGN", "SBUX"]
assert len(TICKERS) == 50 == len(set(TICKERS))
TRAIN = ("2015-01-01", "2025-12-31")
VALID = ("2026-01-01", "2026-06-30")
out_csv = sys.argv[1]

t0 = time.time()
raw = yf.download(TICKERS + ["SPY", "^VIX"], start="2014-01-01", end="2026-10-01", auto_adjust=False,
                  progress=False, group_by="ticker", threads=True)
print("downloaded in %.0fs" % (time.time() - t0))

spy = raw["SPY"]["Adj Close"].dropna()
vix = raw["^VIX"]["Adj Close"].dropna()
mkt = pd.DataFrame({
    "spy_ret_5d": spy / spy.shift(5) - 1,
    "spy_ret_20d": spy / spy.shift(20) - 1,
    "spy_close_to_ma50": spy / spy.rolling(50).mean(),
    "vix_level": vix.reindex(spy.index).ffill(),
    "vix_chg_5d": (vix / vix.shift(5) - 1).reindex(spy.index).ffill(),
})

rows, skipped = [], []
valid_end = pd.Timestamp(VALID[1])
for t in TICKERS:
    df = raw[t][["Open", "High", "Low", "Close", "Adj Close", "Volume"]].dropna()
    if len(df) < 1000:
        skipped.append(t)
        continue
    high, low = adjusted_high_low(df)
    vol = df["Volume"].to_numpy(float)
    for i, d in enumerate(df.index):
        if i + HORIZON >= len(df) or i < 200:
            continue
        if pd.Timestamp(TRAIN[0]) <= d <= pd.Timestamp(TRAIN[1]):
            split = "train"
            if df.index[i + HORIZON] >= pd.Timestamp(VALID[0]):
                continue            # label would use validation-period prices
        elif pd.Timestamp(VALID[0]) <= d <= valid_end:
            split = "validation"
        else:
            continue
        label = label_setup(df, i, high, low)
        if label is None:
            continue
        f = features_at(df, i)
        m = mkt.loc[:d].iloc[-1]
        rows.append({"ticker": t, "date": d, "split": split, "label": label, **f, **m.to_dict(),
                     "rel_ret_20d": f["ret_20d"] - m["spy_ret_20d"],
                     "vol_ratio_20d": vol[i] / vol[i - 20:i].mean(),
                     "vol_ratio_5d": vol[i] / vol[i - 5:i].mean()})
X = pd.DataFrame(rows)
X.to_csv(out_csv, index=False)
print("tickers used: %d (skipped: %s)" % (X.ticker.nunique(), skipped or "none"))
for s in ("train", "validation"):
    part = X[X.split == s]
    print("%-10s setups %6d | positive rate %.1f%% | dates %s..%s" % (s, len(part), 100 * part.label.mean(),
          part.date.min().date(), part.date.max().date()))

MARKET = ["spy_ret_5d", "spy_ret_20d", "spy_close_to_ma50", "vix_level", "vix_chg_5d", "rel_ret_20d"]
VOLUME = ["vol_ratio_20d", "vol_ratio_5d"]
SETS = {"price only (7)": list(FEATURE_NAMES),
        "price + market (PRIMARY)": list(FEATURE_NAMES) + MARKET,
        "price + market + volume": list(FEATURE_NAMES) + MARKET + VOLUME}
tr, va = X[X.split == "train"], X[X.split == "validation"]
print("\n| Features | Model | Validation AUC | 90% interval |\n|---|---|---|---|")
for name, cols in SETS.items():
    preds = {}
    for mname, model in models().items():
        if mname == "Base rate":
            continue
        model.fit(tr[cols], tr.label)
        preds[mname] = model.predict_proba(va[cols])[:, 1]
    ci = block_bootstrap(va.date.dt.strftime("%Y-%m-%d"), va.label.to_numpy(), preds)
    for mname, p in preds.items():
        print("| %s | %s | %.3f | %.3f-%.3f |" % (name, mname, scores(va.label.to_numpy(), p)["auc"], *ci[mname]["auc"]))
    if name.endswith("(PRIMARY)"):
        p = preds["Gradient boosting"]
        top = va.assign(p=p).sort_values("p", ascending=False)
        for share in (0.1, 0.2):
            k = int(len(top) * share)
            print("|  | GB top %d%% of validation setups: win rate %.1f%% (all: %.1f%%, break-even 37.5%%) | | |"
                  % (share * 100, 100 * top.label.iloc[:k].mean(), 100 * va.label.mean()))
