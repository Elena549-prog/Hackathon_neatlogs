"""Step 3: label every setup day, add its features, and assign it to a time split.

Usage (from the repo root, after Step 2): python src/labels.py

Writes data/labels/setups.csv and runs/label_summary.md.
Exits with status 1 if any split's positive rate is outside 10-90% (SPEC: stop and report).
"""
import os
import sys

import numpy as np
import pandas as pd

if __package__ in (None, ""):  # allow `python src/labels.py` as well as `import src.labels`
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.data import TICKERS, load_prices
from src.features import FEATURE_NAMES, features_at

# Frozen in SPEC section 0. Do not change.
HORIZON = 10            # trading days t+1 .. t+10
TARGET = 0.05           # +5%
STOP = 0.03             # -3%
SPLITS = [              # (name, first setup date, last setup date), both inclusive
    ("train", "2024-10-01", "2025-12-31"),
    ("validation", "2026-01-01", "2026-06-30"),
    ("test", "2026-07-01", "2026-09-15"),
]
MIN_POS_RATE, MAX_POS_RATE = 0.10, 0.90

SETUPS_PATH = os.path.join("data", "labels", "setups.csv")
SUMMARY_PATH = os.path.join("runs", "label_summary.md")


def make_setups(prices_df, ticker=None):
    """One row per trading day t that has 10 trading days after it in the data."""
    n_setups = max(0, len(prices_df) - HORIZON)
    return pd.DataFrame({"ticker": ticker, "date": prices_df.index[:n_setups]})


def adjusted_high_low(prices_df):
    """High and Low on the same scale as Adj Close.

    Yahoo's High/Low are raw prices, but the entry price is the *adjusted* close, which is
    lower than the raw close for dividend payers (about 1.5% for MSFT at the start of the
    window). Comparing raw highs against an adjusted entry would count a +3.5% move as +5%.
    Scaling each day's High/Low by that day's Adj Close / Close puts both on one scale.
    """
    factor = prices_df["Adj Close"] / prices_df["Close"]
    return prices_df["High"] * factor, prices_df["Low"] * factor


def label_setup(prices_df, t_index, high=None, low=None):
    """1 if +5% is hit before -3% within the next 10 trading days, 0 if -3% comes first
    or both happen on the same day, None if neither happens (the setup is dropped).

    `high`/`low` default to adjusted_high_low(prices_df); pass them in to avoid
    recomputing for every setup.
    """
    if t_index + HORIZON >= len(prices_df):
        raise ValueError("setup at row %d has no t+%d in the data" % (t_index, HORIZON))
    if high is None or low is None:
        high, low = adjusted_high_low(prices_df)
    entry = prices_df["Adj Close"].iloc[t_index]
    up, down = entry * (1 + TARGET), entry * (1 - STOP)
    for i in range(t_index + 1, t_index + HORIZON + 1):
        hit_up = high.iloc[i] >= up
        hit_down = low.iloc[i] <= down
        if hit_down:          # covers "down first" and "both on the same day" (conservative)
            return 0
        if hit_up:
            return 1
    return None


def split_for(date):
    """The split a setup date belongs to, or None if it falls outside all of them."""
    for name, start, end in SPLITS:
        if pd.Timestamp(start) <= date <= pd.Timestamp(end):
            return name
    return None


def build_setups(prices_by_ticker):
    """The full labeled table: ticker, date, split, label, features. Also returns drop counts."""
    rows, dropped = [], {"no_split": 0, "no_label": 0, "short_history": 0,
                         "raw_hilo_differs": 0, "raw_hilo_checked": 0}
    for ticker, df in prices_by_ticker.items():
        high, low = adjusted_high_low(df)
        for t_index, date in enumerate(make_setups(df, ticker)["date"]):
            split = split_for(date)
            if split is None:
                dropped["no_split"] += 1
                continue
            feats = features_at(df, t_index)
            if any(np.isnan(v) for v in feats.values()):
                dropped["short_history"] += 1
                continue
            label = label_setup(df, t_index, high, low)
            if split in ("train", "validation"):  # how much the High/Low scaling matters
                dropped["raw_hilo_checked"] += 1
                dropped["raw_hilo_differs"] += label != label_setup(df, t_index, df["High"], df["Low"])
            if label is None:
                dropped["no_label"] += 1
                continue
            rows.append({"ticker": ticker, "date": date.date().isoformat(), "split": split,
                         "label": label, **feats})
    columns = ["ticker", "date", "split", "label"] + FEATURE_NAMES
    return pd.DataFrame(rows, columns=columns), dropped


def summarize(setups, dropped):
    """Markdown summary. Test split: overall count and positive rate only (SPEC rule)."""
    lines = ["# Label summary (Step 3)", "",
             "Rule: label 1 if adjusted High reaches entry x 1.05 before adjusted Low reaches "
             "entry x 0.97 within 10 trading days; 0 if the stop comes first or both on one day; "
             "dropped if neither.", "",
             "Interpretation to confirm with the owner: SPEC says entry = Adj Close and hit checks use "
             "High/Low. Yahoo's High/Low are unadjusted, so they are scaled by each day's "
             "Adj Close / Close to match the entry. Using raw High/Low instead would change "
             "%d of %d train+validation setups (label differs or the setup would be dropped/kept)."
             % (dropped["raw_hilo_differs"], dropped["raw_hilo_checked"]), "",
             "## Per split", "", "| Split | Setups | Positives | Positive rate | Date range |",
             "|---|---|---|---|---|"]
    for name, _, _ in SPLITS:
        s = setups[setups["split"] == name]
        rate = s["label"].mean() if len(s) else float("nan")
        span = "%s to %s" % (s["date"].min(), s["date"].max()) if len(s) else "-"
        lines.append("| %s | %d | %d | %.1f%% | %s |" % (name, len(s), s["label"].sum(), 100 * rate, span))
    lines += ["", "## Per ticker (train and validation only)", "",
              "| Ticker | Train setups | Train positive rate | Validation setups | Validation positive rate |",
              "|---|---|---|---|---|"]
    for t in setups["ticker"].unique():
        cells = []
        for name in ("train", "validation"):
            s = setups[(setups["ticker"] == t) & (setups["split"] == name)]
            cells += [str(len(s)), "%.1f%%" % (100 * s["label"].mean()) if len(s) else "-"]
        lines.append("| %s | %s |" % (t, " | ".join(cells)))
    lines += ["", "Test-split rows are kept in setups.csv but only their overall positive rate is "
              "reported here, as SPEC section 0 requires.", "",
              "## Dropped setups", "",
              "- Before 200 days of history (200-day average not available): %d" % dropped["short_history"],
              "- Neither +5%% nor -3%% hit within 10 days: %d" % dropped["no_label"],
              "- Date outside all splits (feature-history year before 2024-10-01, or after "
              "2026-09-15): %d" % dropped["no_split"]]
    return "\n".join(lines) + "\n"


def main():
    prices = {t: load_prices(t) for t in TICKERS}
    setups, dropped = build_setups(prices)
    os.makedirs(os.path.dirname(SETUPS_PATH), exist_ok=True)
    setups.to_csv(SETUPS_PATH, index=False)
    summary = summarize(setups, dropped)
    os.makedirs(os.path.dirname(SUMMARY_PATH), exist_ok=True)
    with open(SUMMARY_PATH, "w", encoding="utf-8") as f:
        f.write(summary)
    print(summary)

    bad = []
    for name, _, _ in SPLITS:
        s = setups[setups["split"] == name]
        if not len(s) or not MIN_POS_RATE <= s["label"].mean() <= MAX_POS_RATE:
            bad.append(name)
    if bad:
        print("STOP: positive rate outside 10-90%% (or no setups) in: %s. Report; do not change thresholds."
              % ", ".join(bad))
        sys.exit(1)


if __name__ == "__main__":
    main()
