"""Step 2: download daily price history for the 5 tickers and check it.

Usage (from the repo root, venv active, needs internet access to Yahoo Finance):
    python src/data.py

Writes data/prices/<TICKER>.csv and runs/price_data_check.md.
Exits with status 1 if any ticker fails a check (SPEC: stop and report, do not replace tickers).
"""
import os
import sys

import numpy as np
import pandas as pd

# SPEC section 0 (updated 2026-10-10, see the change log there). Do not change without the owner.
TICKERS = ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA"]
# Starts one year before the first setup date (2024-10-01) so that features needing
# 200 days of history (the 200-day average) exist from the first train setup on.
# The extra year is feature history only: no setups are made before 2024-10-01.
START = "2023-10-01"
END = "2026-10-01"  # exclusive, so the last day is 2026-09-30
COLUMNS = ["Open", "High", "Low", "Close", "Adj Close", "Volume"]

PRICES_DIR = os.path.join("data", "prices")
REPORT_PATH = os.path.join("runs", "price_data_check.md")

# Check thresholds. US markets trade about 252 days a year, so the 3-year window
# holds about 753 trading days. A small shortfall at the edges is fine.
MIN_ROWS = 730
MAX_ROWS = 760
MAX_GAP_TRADING_DAYS = 5


def download_prices(ticker, start=START, end=END):
    """Daily prices for one ticker: a DataFrame indexed by date with COLUMNS."""
    import yfinance as yf

    df = yf.download(ticker, start=start, end=end, auto_adjust=False, progress=False,
                     multi_level_index=False)
    if df is None or df.empty:
        raise RuntimeError("no data returned for %s" % ticker)
    missing = [c for c in COLUMNS if c not in df.columns]
    if missing:
        raise RuntimeError("%s: missing columns %s (got %s)" % (ticker, missing, list(df.columns)))
    df = df[COLUMNS].copy()
    df.index = pd.to_datetime(df.index).tz_localize(None).normalize()
    df.index.name = "Date"
    return df.sort_index()


def load_prices(ticker, prices_dir=PRICES_DIR):
    """Read a saved CSV back in the same shape download_prices returns."""
    path = os.path.join(prices_dir, "%s.csv" % ticker)
    return pd.read_csv(path, index_col="Date", parse_dates=["Date"])


# ------------------------------------------------------------------------------- checks
# Each check returns a list of problem descriptions; an empty list means it passed.

def check_row_count(df, min_rows=MIN_ROWS, max_rows=MAX_ROWS):
    n = len(df)
    if n < min_rows or n > max_rows:
        return ["row count %d outside expected range %d-%d" % (n, min_rows, max_rows)]
    return []


def check_no_missing_adj_close(df):
    n = int(df["Adj Close"].isna().sum())
    return ["%d missing Adj Close value(s)" % n] if n else []


def check_no_duplicate_dates(df):
    dups = df.index[df.index.duplicated()]
    return ["duplicate date(s): %s" % ", ".join(str(d.date()) for d in dups)] if len(dups) else []


def find_gaps(df, max_gap=MAX_GAP_TRADING_DAYS):
    """Runs of more than `max_gap` missing weekdays between consecutive rows.

    Uses weekdays (Mon-Fri) as a stand-in for trading days. Market holidays only remove
    one or two weekdays at a time, so they never come close to a 5-day gap.
    Returns a list of (last_date_before, first_date_after, missing_weekdays).
    """
    dates = df.index.sort_values().unique()
    gaps = []
    for prev, nxt in zip(dates[:-1], dates[1:]):
        # Weekdays strictly between prev and nxt.
        missing = int(np.busday_count(prev.date(), nxt.date())) - 1
        if missing > max_gap:
            gaps.append((prev, nxt, missing))
    return gaps


def check_no_long_gaps(df, max_gap=MAX_GAP_TRADING_DAYS):
    return ["gap of %d weekdays between %s and %s" % (m, a.date(), b.date())
            for a, b, m in find_gaps(df, max_gap)]


def run_checks(df):
    """All Step 2 checks for one ticker's DataFrame."""
    return (check_row_count(df) + check_no_missing_adj_close(df)
            + check_no_duplicate_dates(df) + check_no_long_gaps(df))


# --------------------------------------------------------------------------------- main

def write_report(results, path=REPORT_PATH):
    lines = [
        "# Price data check (Step 2)",
        "",
        "Source: Yahoo Finance via yfinance, `auto_adjust=False`, %s to %s (end exclusive)." % (START, END),
        "",
        "| Ticker | Rows | First date | Last date | Problems |",
        "|---|---|---|---|---|",
    ]
    for ticker, r in results.items():
        problems = "; ".join(r["problems"]) if r["problems"] else "none"
        lines.append("| %s | %s | %s | %s | %s |" % (ticker, r["rows"], r["first"], r["last"], problems))
    lines += ["", "Checks: row count %d-%d, no missing Adj Close, no duplicate dates, "
              "no gap longer than %d weekdays." % (MIN_ROWS, MAX_ROWS, MAX_GAP_TRADING_DAYS)]
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    return "\n".join(lines)


def main():
    os.makedirs(PRICES_DIR, exist_ok=True)
    results = {}
    for ticker in TICKERS:
        try:
            df = download_prices(ticker)
        except Exception as e:  # report and keep going so every ticker is covered
            results[ticker] = {"rows": 0, "first": "-", "last": "-", "problems": ["download failed: %s" % e]}
            continue
        df.to_csv(os.path.join(PRICES_DIR, "%s.csv" % ticker))
        results[ticker] = {
            "rows": len(df),
            "first": str(df.index.min().date()),
            "last": str(df.index.max().date()),
            "problems": run_checks(df),
        }
    print(write_report(results))
    failed = [t for t, r in results.items() if r["problems"]]
    if failed:
        print("\nFAILED: %s. Stop and report; do not replace tickers." % ", ".join(failed))
        sys.exit(1)
    print("\nAll %d tickers passed." % len(TICKERS))


if __name__ == "__main__":
    main()
