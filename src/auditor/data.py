"""Researcher (code): fetch and cache data, build features, report coverage (spec sections 3, 6).

Sources:
- Prices: Yahoo via yfinance, auto_adjust=False (both Close and Adj Close), for the group's tickers
  plus SPY and ^VIX, 2014-01-01 to 2026-07-30 (exclusive). Cache: data/cache/prices/<TICKER>.csv.
- Implied vol: DoltHub post-no-preference/options volatility_history, 2019-06-01 to 2026-06-30,
  queried in 14-day date windows for all tickers at once. Cache: data/cache/iv_50.csv (the
  straddle spike's cache, same columns) or data/cache/iv_auditor.csv.
- Earnings dates: yfinance get_earnings_dates(limit=60). Cache: data/cache/earnings.json.

Network calls go through a Fetchers object so tests can replace them. Prices after 2026-06-30
are only used for validation exits; no setup is ever built after the validation window.
"""
import json
import math
import os
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from src.auditor.plan import GROUPS, STRADDLES

PRICE_START, PRICE_END = "2014-01-01", "2026-07-30"        # end exclusive: 20 trading days past 2026-06-30
IV_START, IV_END = "2019-06-01", "2026-06-30"
TRAIN_START, STRADDLE_TRAIN_START, TRAIN_END = "2015-01-01", "2020-01-01", "2025-12-31"
VALID_START, VALID_END = "2026-01-01", "2026-06-30"
IV_STALE_DAYS = 5
IV_WINDOW_DAYS = 14
MARKET = ("SPY", "^VIX")
CACHE_DIR = os.path.join("data", "cache")
DOLTHUB_API = "https://www.dolthub.com/api/v1alpha1/post-no-preference/options/master?q="


class DataError(Exception):
    pass


class LeakageError(Exception):
    pass


# ----------------------------------------------------------------------------------- fetchers

class Fetchers:
    """Real network access. Tests pass an object with the same three methods."""

    def prices(self, tickers, start, end):
        import yfinance as yf
        raw = yf.download(list(tickers), start=start, end=end, auto_adjust=False, progress=False,
                          group_by="ticker", threads=True)
        out = {}
        for t in tickers:
            try:
                df = raw[t][["Open", "High", "Low", "Close", "Adj Close", "Volume"]].dropna(how="all")
            except KeyError:
                continue
            if len(df):
                df.index = pd.to_datetime(df.index).tz_localize(None).normalize()
                df.index.name = "Date"
                out[t] = df
        return out

    def dolthub(self, sql, timeout=60):
        """Rows of one DoltHub query. Raises TimeoutError on a timeout, RuntimeError on a row limit."""
        try:
            with urllib.request.urlopen(DOLTHUB_API + urllib.parse.quote(sql), timeout=timeout) as r:
                d = json.load(r)
        except (TimeoutError, OSError) as e:
            raise TimeoutError(str(e)) from e
        status = d.get("query_execution_status")
        if status == "RowLimit":
            raise RuntimeError("row limit")
        if status != "Success":
            raise TimeoutError("DoltHub status %s: %s" % (status, d.get("query_execution_message", "")))
        return d["rows"]

    def earnings(self, ticker):
        import yfinance as yf
        df = yf.Ticker(ticker).get_earnings_dates(limit=60)
        if df is None or not len(df):
            return []
        idx = pd.to_datetime(df.index)
        if idx.tz is not None:
            idx = idx.tz_localize(None)
        return sorted({d.date().isoformat() for d in idx})


# ------------------------------------------------------------------------------------- prices

def _price_path(cache_dir, ticker):
    return os.path.join(cache_dir, "prices", "%s.csv" % ticker)


def _covers(df):
    return len(df) and df.index[0] <= pd.Timestamp(PRICE_START) + pd.Timedelta(days=10) \
        and df.index[-1] >= pd.Timestamp(PRICE_END) - pd.Timedelta(days=10)


def load_prices(tickers, fetch, cache_dir=CACHE_DIR, log=None):
    """{ticker: OHLCV DataFrame}. Cached per ticker; missing ones fetched in one call."""
    out, missing = {}, []
    for t in tickers:
        path = _price_path(cache_dir, t)
        if os.path.exists(path):
            df = pd.read_csv(path, index_col="Date", parse_dates=["Date"])
            if _covers(df):
                out[t] = df
                continue
        missing.append(t)
    if missing:
        if log:
            log("tool_called", "researcher", tool="get_prices", args={"tickers": len(missing)})
        got = fetch.prices(missing, PRICE_START, PRICE_END)
        os.makedirs(os.path.join(cache_dir, "prices"), exist_ok=True)
        for t, df in got.items():
            df = df.loc[:pd.Timestamp(PRICE_END) - pd.Timedelta(days=1)]
            df.to_csv(_price_path(cache_dir, t))
            out[t] = df
    return out


# --------------------------------------------------------------------------------- implied vol

def _iv_cache(cache_dir, tickers):
    """The first cache file that covers every ticker over the implied-vol window, else None."""
    for name in ("iv_auditor.csv", "iv_50.csv"):
        path = os.path.join(cache_dir, name)
        if not os.path.exists(path):
            continue
        iv = pd.read_csv(path, parse_dates=["date"])
        have = set(iv["ticker"])
        if set(tickers) <= have and iv["date"].min() <= pd.Timestamp(IV_START) + pd.Timedelta(days=10) \
                and iv["date"].max() >= pd.Timestamp(IV_END) - pd.Timedelta(days=10):
            return iv[iv["ticker"].isin(tickers)]
    return None


def fetch_iv_window(fetch, tickers, a, b, sleep=time.sleep, retries=3, on_recovered=None, fault=None):
    """Rows for [a, b]. Retries with backoff; on repeated timeouts (or a row limit), halves the window.

    `fault` is a one-element list; if it holds "dolthub_timeout", the first attempt raises a
    timeout and the fault is consumed (spec section 6, fault injection).
    """
    syms = ",".join("'%s'" % t.replace("-", ".") for t in tickers)
    sql = ("SELECT date, act_symbol, iv_current, hv_current FROM volatility_history WHERE date BETWEEN "
           "'%s' AND '%s' AND act_symbol IN (%s)" % (a.date(), b.date(), syms))
    failed = None
    for attempt in range(retries):
        try:
            if fault and fault[0] == "dolthub_timeout":
                fault[0] = None
                raise TimeoutError("injected DoltHub timeout")
            rows = fetch.dolthub(sql)
            if failed and on_recovered:
                on_recovered("DoltHub query %s..%s: %s" % (a.date(), b.date(), failed),
                             "retried after backoff", "injected" in failed)
            return rows
        except RuntimeError:           # row limit: only a smaller window helps
            failed = "row limit"
            break
        except TimeoutError as e:
            failed = str(e)
            sleep(2 * (attempt + 1))
    if b <= a:
        raise DataError("DoltHub query for %s keeps failing: %s" % (a.date(), failed))
    mid = a + (b - a) // 2
    left = fetch_iv_window(fetch, tickers, a, mid, sleep, retries, None, fault)
    right = fetch_iv_window(fetch, tickers, mid + pd.Timedelta(days=1), b, sleep, retries, None, fault)
    if on_recovered:
        on_recovered("DoltHub query %s..%s: %s" % (a.date(), b.date(), failed),
                     "halved the window to %s..%s and %s..%s" % (a.date(), mid.date(),
                                                                  (mid + pd.Timedelta(days=1)).date(), b.date()),
                     "injected" in (failed or ""))
    return left + right


def load_iv(tickers, fetch, cache_dir=CACHE_DIR, log=None, on_recovered=None, fault=None, sleep=time.sleep):
    """DataFrame date, ticker, iv_current, hv_current for the tickers over the implied-vol window."""
    if fault and fault[0] == "dolthub_timeout":
        # The injected fault fires on the first DoltHub fetch, cache or not, so recovery is always shown.
        rows = fetch_iv_window(fetch, tickers, pd.Timestamp(IV_END) - pd.Timedelta(days=IV_WINDOW_DAYS - 1),
                               pd.Timestamp(IV_END), sleep=sleep, on_recovered=on_recovered, fault=fault)
        cached = _iv_cache(cache_dir, tickers)
        if cached is not None:
            return cached
        recent = _iv_frame(rows)
    else:
        cached = _iv_cache(cache_dir, tickers)
        if cached is not None:
            return cached
        recent = None
    if log:
        log("tool_called", "researcher", tool="get_implied_vol", args={"tickers": len(tickers)})
    starts = pd.date_range(IV_START, IV_END, freq="%dD" % IV_WINDOW_DAYS)
    parts = []
    for i, a in enumerate(starts):
        b = min(a + pd.Timedelta(days=IV_WINDOW_DAYS - 1), pd.Timestamp(IV_END))
        parts.extend(fetch_iv_window(fetch, tickers, a, b, sleep=sleep, on_recovered=on_recovered, fault=fault))
        if log and i % 20 == 0:
            log("data_progress", "researcher", what="implied vol", percent=round(100 * (i + 1) / len(starts)))
    iv = _iv_frame(parts)
    if recent is not None:
        iv = pd.concat([iv, recent]).drop_duplicates(["date", "ticker"])
    os.makedirs(cache_dir, exist_ok=True)
    iv.to_csv(os.path.join(cache_dir, "iv_auditor.csv"), index=False)
    return iv


def _iv_frame(rows):
    iv = pd.DataFrame(rows, columns=["date", "act_symbol", "iv_current", "hv_current"])
    iv["ticker"] = iv.pop("act_symbol").str.replace(".", "-", regex=False)
    iv["date"] = pd.to_datetime(iv["date"])
    for c in ("iv_current", "hv_current"):
        iv[c] = pd.to_numeric(iv[c], errors="coerce")
    return iv


# ------------------------------------------------------------------------------------ earnings

def load_earnings(tickers, fetch, cache_dir=CACHE_DIR, log=None):
    """{ticker: sorted list of ISO dates} ([] = no coverage)."""
    path = os.path.join(cache_dir, "earnings.json")
    cache = {}
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            cache = json.load(f)
    missing = [t for t in tickers if t not in cache]
    if missing:
        if log:
            log("tool_called", "researcher", tool="get_earnings_dates", args={"tickers": len(missing)})
        for t in missing:
            try:
                cache[t] = fetch.earnings(t)
            except Exception:            # no coverage for this ticker; reported, F1 leaves it out
                cache[t] = []
        os.makedirs(cache_dir, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(cache, f, indent=1, sort_keys=True)
    return {t: cache.get(t, []) for t in tickers}


# ------------------------------------------------------------------------------------ features

def adjusted_ohl(df):
    """Open, High and Low on the Adj Close scale (same factor as src/labels.py adjusted_high_low)."""
    factor = df["Adj Close"] / df["Close"]
    return df["Open"] * factor, df["High"] * factor, df["Low"] * factor


def price_features(df):
    """Vectorized src/features.py: equal to features_at(df, i) for every row i (tested)."""
    adj = df["Adj Close"].astype(float)
    out = pd.DataFrame(index=df.index)
    for k in (1, 5, 10, 20):
        out["ret_%dd" % k] = adj / adj.shift(k) - 1
    out["vol_20d"] = (adj / adj.shift(1) - 1).rolling(20).std(ddof=1)
    out["close_to_ma50"] = adj / adj.rolling(50).mean()
    out["close_to_ma200"] = adj / adj.rolling(200).mean()
    vol = df["Volume"].astype(float)
    out["vol_ratio_5d"] = vol / vol.shift(1).rolling(5).mean()
    out["vol_ratio_20d"] = vol / vol.shift(1).rolling(20).mean()
    return out


def market_features(spy, vix):
    """Per-date market features from SPY and ^VIX (Adj Close, as in the spike scripts)."""
    s = spy["Adj Close"].astype(float)
    v = vix["Adj Close"].astype(float).reindex(s.index).ffill()
    return pd.DataFrame({"spy_ret_5d": s / s.shift(5) - 1, "spy_ret_20d": s / s.shift(20) - 1,
                         "spy_close_to_ma50": s / s.rolling(50).mean(), "vix_level": v,
                         "vix_chg_5d": v / v.shift(5) - 1}, index=s.index)


def iv_features(dates, iv_rows, vol_20d):
    """Latest implied-vol row on or before each date; NaN (and stale=True) if older than 5 days."""
    rows = iv_rows.dropna(subset=["iv_current"]).sort_values("date")
    left = pd.DataFrame({"date": dates})
    if len(rows):
        m = pd.merge_asof(left, rows[["date", "iv_current", "hv_current"]].assign(iv_date=rows["date"]),
                          on="date", direction="backward")
    else:
        m = left.assign(iv_current=np.nan, hv_current=np.nan, iv_date=pd.NaT)
    age = (m["date"] - m["iv_date"]).dt.days
    stale = age.isna() | (age > IV_STALE_DAYS)
    iv = m["iv_current"].where(~stale).to_numpy(float)
    hv = m["hv_current"].where(~stale).to_numpy(float)
    with np.errstate(divide="ignore", invalid="ignore"):
        ratio = np.where(hv > 0, iv / hv, np.nan)
    out = pd.DataFrame({"iv": iv, "hv": hv, "iv_hv_ratio": ratio,
                        "iv_minus_rv20": iv - np.asarray(vol_20d, float) * math.sqrt(252),
                        "iv_date": m["iv_date"].to_numpy(), "iv_stale": stale.to_numpy()}, index=dates)
    return out


def earnings_features(dates, report_dates, horizon=10):
    """earnings_within_10d and days_since_earnings per trading day. NaN without coverage, and
    before the earliest known report date."""
    n = len(dates)
    within = np.full(n, np.nan)
    since = np.full(n, np.nan)
    if report_dates:
        e = np.array(sorted(pd.to_datetime(report_dates)), dtype="datetime64[ns]")
        d = dates.to_numpy(dtype="datetime64[ns]")
        known = d >= e[0]
        end = d[np.minimum(np.arange(n) + horizon, n - 1)]
        # a report date in (d, end]
        nxt = np.searchsorted(e, d, side="right")
        has_next = nxt < len(e)
        within_v = np.zeros(n)
        within_v[has_next] = (e[nxt[has_next]] <= end[has_next]).astype(float)
        last = np.searchsorted(e, d, side="right") - 1
        pos_last = np.searchsorted(d, e[np.maximum(last, 0)], side="left")
        since_v = np.arange(n) - pos_last
        within[known] = within_v[known]
        since[known & (last >= 0)] = since_v[known & (last >= 0)]
    return pd.DataFrame({"earnings_within_10d": within, "days_since_earnings": since}, index=dates)


# ---------------------------------------------------------------------------------------- panel

@dataclass
class Panel:
    frames: dict                    # ticker -> DataFrame: prices (adjusted OHL), features, iv columns
    calendar: pd.DatetimeIndex      # SPY trading days, used to number 10-trading-day blocks
    earnings: dict                  # ticker -> list of ISO report dates ([] = no coverage)
    coverage: dict = field(default_factory=dict)


def build_panel(family, group, fetch=None, cache_dir=CACHE_DIR, log=None, on_recovered=None,
                fault=None, sleep=time.sleep):
    """Fetch (or load cached) data for one audit and assemble per-ticker frames."""
    fetch = fetch or Fetchers()
    tickers = GROUPS[group]
    raw = load_prices(list(tickers) + list(MARKET), fetch, cache_dir, log)
    for m in MARKET:
        if m not in raw:
            raise DataError("no prices for %s" % m)
    mkt = market_features(raw["SPY"], raw["^VIX"])
    iv = load_iv(tickers, fetch, cache_dir, log, on_recovered, fault, sleep) if family in STRADDLES else None
    earnings = load_earnings(tickers, fetch, cache_dir, log)

    frames, coverage = {}, {"tickers": {}, "missing_prices": []}
    for t in tickers:
        df = raw.get(t)
        if df is None or not len(df):
            coverage["missing_prices"].append(t)
            continue
        df = df.dropna(subset=["Adj Close", "Close"])
        o, h, l = adjusted_ohl(df)
        f = pd.DataFrame({"Open": o, "High": h, "Low": l, "Close": df["Close"].astype(float),
                          "Adj Close": df["Adj Close"].astype(float)}, index=df.index)
        f = f.join(price_features(df))
        f = f.join(mkt.reindex(f.index, method="ffill"))
        f["rel_ret_20d"] = f["ret_20d"] - f["spy_ret_20d"]
        if iv is not None:
            f = f.join(iv_features(f.index, iv[iv["ticker"] == t], f["vol_20d"]))
        f = f.join(earnings_features(f.index, earnings.get(t, [])))
        frames[t] = f
        years = f.index.year.value_counts().sort_index()
        coverage["tickers"][t] = {"first": str(f.index[0].date()), "last": str(f.index[-1].date()),
                                  "rows_per_year_min": int(years.loc[2015:2025].min()) if len(years.loc[2015:2025]) else 0,
                                  "earliest_earnings": (earnings.get(t) or [None])[0]}
    coverage["earnings_covered"] = sum(1 for t in tickers if earnings.get(t))
    coverage["iv_rows"] = int(len(iv)) if iv is not None else None
    coverage["gaps"] = [t for t, c in coverage["tickers"].items() if c["rows_per_year_min"] < 240]
    return Panel(frames, raw["SPY"].index, earnings, coverage)
