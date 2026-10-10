"""Step 2 tests.

The first group checks the check functions themselves on small made-up price tables,
so they run anywhere without internet. The second group runs every check on the real
CSVs in data/prices/ and is skipped for a ticker whose file has not been downloaded yet.
"""
import os

import numpy as np
import pandas as pd
import pytest

from src.data import (
    COLUMNS, MAX_ROWS, MIN_ROWS, PRICES_DIR, TICKERS,
    check_no_duplicate_dates, check_no_long_gaps, check_no_missing_adj_close,
    check_row_count, find_gaps, load_prices, run_checks,
)


def make_prices(n=500, start="2024-10-01"):
    """A clean fake price table on consecutive weekdays."""
    dates = pd.bdate_range(start, periods=n, name="Date")
    close = np.linspace(100, 150, n)
    return pd.DataFrame({"Open": close, "High": close * 1.01, "Low": close * 0.99,
                         "Close": close, "Adj Close": close, "Volume": 1_000_000}, index=dates)


# ------------------------------------------------------------ the checks on made-up data

def test_clean_table_passes_every_check():
    assert run_checks(make_prices()) == []


def test_row_count_too_low_and_too_high():
    assert check_row_count(make_prices(MIN_ROWS - 1))
    assert check_row_count(make_prices(MAX_ROWS + 1))
    assert check_row_count(make_prices(MIN_ROWS)) == []


def test_missing_adj_close_is_caught():
    df = make_prices()
    df.iloc[10, df.columns.get_loc("Adj Close")] = np.nan
    assert check_no_missing_adj_close(df) == ["1 missing Adj Close value(s)"]


def test_duplicate_date_is_caught():
    df = make_prices()
    df = pd.concat([df, df.iloc[[5]]])
    assert check_no_duplicate_dates(df)


def test_long_gap_is_caught():
    df = make_prices()
    df = df.drop(df.index[100:106])  # remove 6 trading days in a row
    gaps = find_gaps(df)
    assert len(gaps) == 1 and gaps[0][2] == 6
    assert check_no_long_gaps(df)


def test_short_gap_and_weekends_are_fine():
    df = make_prices()
    df = df.drop(df.index[100:105])  # 5 missing days is allowed
    assert check_no_long_gaps(df) == []


# ------------------------------------------------------------- the real downloaded files

@pytest.mark.parametrize("ticker", TICKERS)
def test_downloaded_file(ticker):
    path = os.path.join(PRICES_DIR, "%s.csv" % ticker)
    if not os.path.exists(path):
        pytest.skip("%s not downloaded yet (run python src/data.py)" % path)
    df = load_prices(ticker)
    assert list(df.columns) == COLUMNS
    assert check_row_count(df) == []
    assert check_no_missing_adj_close(df) == []
    assert check_no_duplicate_dates(df) == []
    assert check_no_long_gaps(df) == []
