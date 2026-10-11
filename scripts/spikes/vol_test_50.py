"""SPIKE (throwaway): is the SIZE of the next 10-day move predictable on 50 stocks?
Target fixed before running: High >= +5% or Low <= -5% within 10 trading days (adjusted High/Low).
Same tickers, splits, models and block bootstrap as signal_test_50.py. Test split untouched."""
import sys, numpy as np, pandas as pd, yfinance as yf
sys.path.insert(0, "."); sys.path.insert(0, sys.argv[1])
from signal_test_50_cfg import TICKERS, TRAIN, VALID
from src.baselines import block_bootstrap, models, scores
from src.features import FEATURE_NAMES, features_at
from src.labels import HORIZON, adjusted_high_low
raw = yf.download(TICKERS + ["SPY", "^VIX"], start="2014-01-01", end="2026-10-01", auto_adjust=False, progress=False, group_by="ticker")
spy, vix = raw["SPY"]["Adj Close"].dropna(), raw["^VIX"]["Adj Close"].dropna()
mkt = pd.DataFrame({"spy_ret_5d": spy / spy.shift(5) - 1, "spy_ret_20d": spy / spy.shift(20) - 1,
                    "spy_close_to_ma50": spy / spy.rolling(50).mean(), "vix_level": vix.reindex(spy.index).ffill(),
                    "vix_chg_5d": (vix / vix.shift(5) - 1).reindex(spy.index).ffill()})
rows = []
for t in TICKERS:
    df = raw[t][["Open", "High", "Low", "Close", "Adj Close", "Volume"]].dropna()
    hi, lo = adjusted_high_low(df); adj = df["Adj Close"].to_numpy(); H, L = hi.to_numpy(), lo.to_numpy()
    mk = mkt.reindex(df.index).to_numpy()
    for i, d in enumerate(df.index):
        if i < 200 or i + HORIZON >= len(df): continue
        if pd.Timestamp(TRAIN[0]) <= d <= pd.Timestamp(TRAIN[1]):
            if df.index[i + HORIZON] >= pd.Timestamp(VALID[0]): continue
            split = "train"
        elif pd.Timestamp(VALID[0]) <= d <= pd.Timestamp(VALID[1]): split = "validation"
        else: continue
        big = int((H[i+1:i+11] >= adj[i] * 1.05).any() or (L[i+1:i+11] <= adj[i] * 0.95).any())
        f = features_at(df, i)
        rows.append({"date": d, "split": split, "y": big, **f, **dict(zip(mkt.columns, mk[i]))})
X = pd.DataFrame(rows).dropna()
cols = list(FEATURE_NAMES) + list(mkt.columns)
tr, va = X[X.split == "train"], X[X.split == "validation"]
print("setups: train %d, validation %d | share with a 5%% move either way: train %.1f%%, validation %.1f%%" % (len(tr), len(va), 100*tr.y.mean(), 100*va.y.mean()))
preds = {}
for name, m in models().items():
    if name == "Base rate": continue
    m.fit(tr[cols], tr.y); preds[name] = m.predict_proba(va[cols])[:, 1]
ci = block_bootstrap(va.date.dt.strftime("%Y-%m-%d"), va.y.to_numpy(), preds)
for name, p in preds.items():
    top = va.y.to_numpy()[np.argsort(-p)]
    print("%-20s validation AUC %.3f (90%% CI %.3f-%.3f) | top 10%%: %.1f%% move | top 20%%: %.1f%% | bottom 20%%: %.1f%%" % (
        name, scores(va.y.to_numpy(), p)["auc"], *ci[name]["auc"], 100*top[:len(top)//10].mean(), 100*top[:len(top)//5].mean(), 100*top[-len(top)//5:].mean()))
