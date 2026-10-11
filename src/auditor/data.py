"""Data tools (AUDITOR_SPEC section 6): prices from Yahoo, implied vol from DoltHub, earnings dates from
Yahoo, and the feature table. All network calls are injectable; everything is cached under data/cache/.

Leakage: features use rows at or before the setup day only (verified against src.features.features_at).
The earnings features use actual report dates (small look-ahead, stated in every report).
"""
import json
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd

from .universe import MARKET

PRICE_START, PRICE_END = "2014-01-01", "2026-07-30"      # end exclusive
IV_START, IV_END = "2019-06-01", "2026-06-30"
IV_MAX_AGE_DAYS = 5
MIN_ROWS = 200
EARNINGS_LIMIT = 60
DOLTHUB_API = "https://www.dolthub.com/api/v1alpha1/post-no-preference/options/master?q="
ROW_LIMIT = 1000
RETRY_SLEEPS = (2, 4, 6, 8)
PRICE_COLUMNS = ["Open", "High", "Low", "Close", "Adj Close", "Volume"]


# ----------------------------------------------------------------------------------------------- prices

def _yf_download(symbols, start, end):
    import yfinance as yf
    return yf.download(list(symbols), start=start, end=end, auto_adjust=False, progress=False,
                       group_by="ticker", threads=True)


def fetch_prices(tickers, cache_dir, download=None):
    """-> ({ticker: OHLCV frame}, skipped). Includes SPY and ^VIX. Tickers under 200 rows are skipped."""
    cache_dir = Path(cache_dir)
    pdir = cache_dir / "prices"
    pdir.mkdir(parents=True, exist_ok=True)
    wanted = list(dict.fromkeys(list(tickers) + MARKET))
    missing = [t for t in wanted if not (pdir / ("%s.csv" % t)).is_file()]
    if missing:
        raw = (download or _yf_download)(missing, PRICE_START, PRICE_END)
        for t in missing:
            try:
                df = raw[t][PRICE_COLUMNS].dropna(how="all") if isinstance(raw.columns, pd.MultiIndex) else raw[PRICE_COLUMNS]
            except KeyError:
                df = pd.DataFrame(columns=PRICE_COLUMNS)
            df.index.name = "Date"
            df.to_csv(pdir / ("%s.csv" % t))
    prices, skipped = {}, []
    for t in wanted:
        df = pd.read_csv(pdir / ("%s.csv" % t), index_col=0, parse_dates=True)
        df = df.dropna(subset=["Close", "Adj Close"])
        if len(df) < MIN_ROWS:
            if t not in MARKET:
                skipped.append(t)
            continue
        prices[t] = df[PRICE_COLUMNS].astype(float)
    return prices, skipped


# ------------------------------------------------------------------------------------------ implied vol

def _symbol(ticker):
    return ticker.replace("-", ".")


def iv_sql(tickers, a, b):
    syms = ",".join("'%s'" % _symbol(t) for t in tickers)
    return ("SELECT date, act_symbol, iv_current, hv_current FROM volatility_history WHERE date BETWEEN '%s' "
            "AND '%s' AND act_symbol IN (%s)" % (a.date(), b.date(), syms))


def window_of(sql):
    """(start, end) timestamps of an iv_sql query (used by tests and by the halving logic)."""
    a, b = re.search(r"BETWEEN '(\d{4}-\d{2}-\d{2})' AND '(\d{4}-\d{2}-\d{2})'", sql).groups()
    return pd.Timestamp(a), pd.Timestamp(b)


def _http_query(sql):
    with urllib.request.urlopen(DOLTHUB_API + urllib.parse.quote(sql), timeout=60) as r:
        d = json.load(r)
    if d.get("query_execution_status") not in ("Success", "RowLimit"):
        raise RuntimeError("DoltHub: %s" % d.get("query_execution_message", "query failed"))
    return d["rows"]


def _is_timeout(e):
    return isinstance(e, TimeoutError) or "timed out" in str(e).lower() or "timeout" in str(e).lower()


def _fetch_window(tickers, a, b, query, sleep, on_recovered):
    """Rows for one date window: retries with backoff; after two timeouts the window is halved."""
    timeouts = 0
    for attempt, pause in enumerate(RETRY_SLEEPS):
        try:
            rows = query(iv_sql(tickers, a, b))
            if len(rows) >= ROW_LIMIT:
                raise RuntimeError("row limit hit for %s..%s" % (a.date(), b.date()))
            return rows
        except Exception as e:
            if not _is_timeout(e):
                raise
            timeouts += 1
            if timeouts >= 2 and (b - a).days >= 2:
                mid = a + (b - a) / 2
                if on_recovered:
                    on_recovered("DoltHub timeout on window %s..%s" % (a.date(), b.date()),
                                 "halved the window and retried")
                return (_fetch_window(tickers, a, mid, query, sleep, on_recovered)
                        + _fetch_window(tickers, mid + pd.Timedelta(days=1), b, query, sleep, on_recovered))
            sleep(pause)
    raise RuntimeError("DoltHub query kept timing out for %s..%s" % (a.date(), b.date()))


def fetch_implied_vol(tickers, cache_dir, query=None, window_days=14, sleep=time.sleep, on_recovered=None,
                      start=IV_START, end=IV_END):
    """-> DataFrame(date, ticker, iv_current, hv_current) for the tickers, cached as cache_dir/iv.csv."""
    cache_dir = Path(cache_dir)
    cache = cache_dir / "iv.csv"
    if cache.is_file():
        iv = pd.read_csv(cache, parse_dates=["date"])
        if set(tickers) <= set(iv.ticker):
            return iv[iv.ticker.isin(tickers)].reset_index(drop=True)
    query = query or _http_query
    rows = []
    a, end_ts = pd.Timestamp(start), pd.Timestamp(end)
    while a <= end_ts:
        b = min(a + pd.Timedelta(days=window_days - 1), end_ts)
        rows += _fetch_window(list(tickers), a, b, query, sleep, on_recovered)
        a = b + pd.Timedelta(days=1)
    iv = pd.DataFrame(rows, columns=["date", "act_symbol", "iv_current", "hv_current"])
    iv["ticker"] = iv.pop("act_symbol").astype(str).str.replace(".", "-", regex=False)
    iv["date"] = pd.to_datetime(iv["date"])
    for c in ("iv_current", "hv_current"):
        iv[c] = pd.to_numeric(iv[c], errors="coerce")
    iv = iv[["date", "ticker", "iv_current", "hv_current"]].sort_values(["ticker", "date"]).reset_index(drop=True)
    if cache.is_file():
        old = pd.read_csv(cache, parse_dates=["date"])
        iv = pd.concat([old[~old.ticker.isin(iv.ticker)], iv]).sort_values(["ticker", "date"]).reset_index(drop=True)
    cache_dir.mkdir(parents=True, exist_ok=True)
    iv.to_csv(cache, index=False)
    return iv[iv.ticker.isin(tickers)].reset_index(drop=True)


# --------------------------------------------------------------------------------------------- earnings

def _yf_earnings(ticker):
    import yfinance as yf
    df = yf.Ticker(ticker).get_earnings_dates(limit=EARNINGS_LIMIT)
    return pd.DatetimeIndex([]) if df is None or df.empty else pd.DatetimeIndex(df.index)


def fetch_earnings(tickers, cache_dir, get_dates=None):
    """-> {ticker: [Timestamp, ...]} of report dates (date only, sorted). Failures give an empty list."""
    cache_dir = Path(cache_dir)
    cache = cache_dir / "earnings.csv"
    known = {}
    if cache.is_file():
        df = pd.read_csv(cache)
        for t, grp in df.groupby("ticker"):
            known[t] = [pd.Timestamp(d) for d in grp["date"] if isinstance(d, str) and d]
        for t in df.ticker.unique():
            known.setdefault(t, [])
    get_dates = get_dates or _yf_earnings
    new_rows = []
    for t in tickers:
        if t in known:
            continue
        try:
            idx = get_dates(t)
            dates = sorted({pd.Timestamp(d).tz_localize(None).normalize() if getattr(d, "tzinfo", None) else pd.Timestamp(d).normalize() for d in idx})
        except Exception:
            dates = []
        known[t] = dates
        new_rows += [{"ticker": t, "date": d.date().isoformat()} for d in dates] or [{"ticker": t, "date": ""}]
    if new_rows:
        cache_dir.mkdir(parents=True, exist_ok=True)
        old = pd.read_csv(cache) if cache.is_file() else pd.DataFrame(columns=["ticker", "date"])
        pd.concat([old, pd.DataFrame(new_rows)]).to_csv(cache, index=False)
    return {t: known.get(t, []) for t in tickers}


# --------------------------------------------------------------------------------------------- features

def _market_features(market):
    spy = market["SPY"]["Adj Close"].astype(float)
    vix = market["^VIX"]["Adj Close"].astype(float).reindex(spy.index).ffill()
    return pd.DataFrame({
        "spy_ret_5d": spy / spy.shift(5) - 1,
        "spy_ret_20d": spy / spy.shift(20) - 1,
        "spy_close_to_ma50": spy / spy.rolling(50).mean(),
        "vix_level": vix,
        "vix_chg_5d": vix / vix.shift(5) - 1,
    })


def _ticker_features(ticker, df, mkt, iv, earnings):
    adj = df["Adj Close"].astype(float)
    vol = df["Volume"].astype(float)
    daily = adj / adj.shift(1) - 1
    out = pd.DataFrame({"ticker": ticker, "date": df.index,
                        "open": df["Open"].to_numpy(float), "high": df["High"].to_numpy(float),
                        "low": df["Low"].to_numpy(float), "close": df["Close"].to_numpy(float),
                        "adj_close": adj.to_numpy(), "volume": vol.to_numpy()})
    for k in (1, 5, 10, 20):
        out["ret_%dd" % k] = (adj / adj.shift(k) - 1).to_numpy()
    out["vol_20d"] = daily.rolling(20).std(ddof=1).to_numpy()
    out["close_to_ma50"] = (adj / adj.rolling(50).mean()).to_numpy()
    out["close_to_ma200"] = (adj / adj.rolling(200).mean()).to_numpy()
    m = mkt.reindex(df.index).ffill()
    for c in m.columns:
        out[c] = m[c].to_numpy()
    out["rel_ret_20d"] = out["ret_20d"] - out["spy_ret_20d"]
    out["vol_ratio_5d"] = (vol / vol.shift(1).rolling(5).mean()).to_numpy()
    out["vol_ratio_20d"] = (vol / vol.shift(1).rolling(20).mean()).to_numpy()
    # implied vol: latest row on or before the day, at most 5 calendar days old
    if iv is not None and len(iv):
        rows = iv[iv.ticker == ticker].dropna(subset=["iv_current"]).sort_values("date")[["date", "iv_current", "hv_current"]]
        merged = pd.merge_asof(out[["date"]].sort_values("date"), rows, on="date", direction="backward",
                               tolerance=pd.Timedelta(days=IV_MAX_AGE_DAYS)) if len(rows) else None
        out["iv"] = merged["iv_current"].to_numpy() if merged is not None else np.nan
        out["hv"] = merged["hv_current"].to_numpy() if merged is not None else np.nan
    else:
        out["iv"], out["hv"] = np.nan, np.nan
    out["iv_hv_ratio"] = out["iv"] / out["hv"].replace(0, np.nan)
    out["iv_minus_rv20"] = out["iv"] - out["vol_20d"] * np.sqrt(252)
    # earnings: trading-day positions of report dates
    dates = earnings.get(ticker) or []
    if dates:
        pos = df.index.searchsorted(pd.DatetimeIndex(dates))           # index of the report day (or the next trading day)
        n = len(df)
        idx = np.arange(n)
        within = np.zeros(n, dtype=float)
        since = np.full(n, np.nan)
        for p in pos:
            if p >= n:
                continue
            within[(idx >= p - 10) & (idx < p)] = 1.0
            after = idx >= p
            since[after] = np.where(np.isnan(since[after]), idx[after] - p, np.minimum(since[after], idx[after] - p))
        out["earnings_within_10d"], out["days_since_earnings"] = within, since
    else:
        out["earnings_within_10d"], out["days_since_earnings"] = np.nan, np.nan
    return out.iloc[MIN_ROWS - 1:]


def build_features(prices, market, iv, earnings):
    """One row per ticker-day with at least 200 rows of history; columns per the section 6 table."""
    mkt = _market_features(market)
    parts = [_ticker_features(t, df, mkt, iv, earnings) for t, df in prices.items() if t not in MARKET]
    if not parts:
        return pd.DataFrame(columns=["ticker", "date"])
    return pd.concat(parts, ignore_index=True)


def coverage(prices, skipped, iv, earnings):
    rows = {}
    for t, df in prices.items():
        if t in MARKET:
            continue
        counts = df.groupby(df.index.year).size()
        rows[t] = {str(y): int(c) for y, c in counts.items()}
    return {
        "rows_per_ticker_year": rows,
        "skipped": list(skipped),
        "iv_rows": int(len(iv)) if iv is not None else 0,
        "iv_range": [iv.date.min().date().isoformat(), iv.date.max().date().isoformat()] if iv is not None and len(iv) else None,
        "earnings_first_date": {t: d[0].date().isoformat() for t, d in earnings.items() if d},
        "tickers_without_earnings": sorted(t for t, d in earnings.items() if not d),
    }
