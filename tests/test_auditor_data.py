"""Data fetchers and vectorised features (AUDITOR_SPEC section 6). No network."""
import numpy as np
import pandas as pd
import pytest

from src.auditor import data
from src.features import features_at


def walk(n, seed=0, start="2024-01-02", level=100.0, volume=1_000_000):
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range(start, periods=n)
    adj = level * np.cumprod(1 + rng.normal(0, 0.01, n))
    close = adj * 1.02                                   # Adj Close below Close, like a dividend payer
    return pd.DataFrame({"Open": close * 0.999, "High": close * 1.01, "Low": close * 0.99, "Close": close,
                         "Adj Close": adj, "Volume": volume * (1 + rng.random(n))}, index=dates)


def market(n, start="2024-01-02"):
    spy, vix = walk(n, seed=7, start=start), walk(n, seed=8, start=start, level=20)
    return {"SPY": spy, "^VIX": vix}


def test_features_match_features_at():
    df = walk(400)
    feats = data.build_features({"AAA": df}, market(400), None, {})
    row = feats[(feats.ticker == "AAA") & (feats.date == df.index[300])].iloc[0]
    ref = features_at(df, 300)
    for k, v in ref.items():
        assert abs(row[k] - v) < 1e-9, k
    assert feats.date.min() == df.index[199]             # 200 rows of history needed


def test_market_and_volume_features():
    df, mkt = walk(260), market(260)
    feats = data.build_features({"AAA": df}, mkt, None, {})
    row = feats[feats.date == df.index[250]].iloc[0]
    vol = df["Volume"].to_numpy()
    assert abs(row.vol_ratio_5d - vol[250] / vol[245:250].mean()) < 1e-9
    assert abs(row.vol_ratio_20d - vol[250] / vol[230:250].mean()) < 1e-9
    spy = mkt["SPY"]["Adj Close"].to_numpy()
    assert abs(row.spy_ret_20d - (spy[250] / spy[230] - 1)) < 1e-9
    assert abs(row.rel_ret_20d - (row.ret_20d - row.spy_ret_20d)) < 1e-12
    vix = mkt["^VIX"]["Adj Close"].to_numpy()
    assert abs(row.vix_level - vix[250]) < 1e-9 and abs(row.vix_chg_5d - (vix[250] / vix[245] - 1)) < 1e-9
    assert abs(row.spy_close_to_ma50 - spy[250] / spy[201:251].mean()) < 1e-9


def test_iv_features_respect_staleness():
    df = walk(400)
    d204 = df.index[204]                                   # a Monday; the IV row is dated the Wednesday before
    iv = pd.DataFrame({"date": [d204 - pd.Timedelta(days=5)], "ticker": ["AAA"], "iv_current": [0.30], "hv_current": [0.20]})
    feats = data.build_features({"AAA": df}, market(400), iv, {})
    at = lambda i: feats[feats.date == df.index[i]].iloc[0]
    assert abs(at(204).iv - 0.30) < 1e-12 and abs(at(204).iv_hv_ratio - 1.5) < 1e-12      # 5 days old: used
    assert abs(at(204).iv_minus_rv20 - (0.30 - at(204).vol_20d * np.sqrt(252))) < 1e-9
    assert np.isnan(at(205).iv) and np.isnan(at(211).iv)                                   # 6 and 12 days old: stale


def test_earnings_features():
    df = walk(400)
    feats = data.build_features({"AAA": df}, market(400), None, {"AAA": [df.index[310]]})
    at = lambda i: feats[feats.date == df.index[i]].iloc[0]
    assert at(300).earnings_within_10d == 1 and at(299).earnings_within_10d == 0 and at(310).earnings_within_10d == 0
    assert at(315).days_since_earnings == 5 and np.isnan(at(300).days_since_earnings)
    none = data.build_features({"AAA": df}, market(400), None, {})
    assert np.isnan(none.iloc[-1].days_since_earnings) and np.isnan(none.iloc[-1].earnings_within_10d)


def test_short_history_ticker_is_skipped(tmp_path):
    frames = {"AAA": walk(400), "BBB": walk(150, seed=1), "SPY": walk(400, seed=7), "^VIX": walk(400, seed=8)}
    prices, skipped = data.fetch_prices(["AAA", "BBB"], tmp_path, download=lambda syms, start, end: _raw(frames, syms))
    assert skipped == ["BBB"] and set(prices) == {"AAA", "SPY", "^VIX"}
    feats = data.build_features(prices, market(400), None, {})
    assert set(feats.ticker) == {"AAA"}


def _raw(frames, symbols):
    return pd.concat({s: frames[s] for s in symbols}, axis=1)


def test_prices_cached(tmp_path):
    frames = {"AAA": walk(400), "SPY": walk(400, seed=7), "^VIX": walk(400, seed=8)}
    calls = []

    def download(syms, start, end):
        calls.append(list(syms))
        return _raw(frames, syms)

    p1, _ = data.fetch_prices(["AAA"], tmp_path, download=download)
    p2, _ = data.fetch_prices(["AAA"], tmp_path, download=download)
    assert len(calls) == 1 and p1["AAA"].equals(p2["AAA"]) and "SPY" in p2 and "^VIX" in p2


def test_dolthub_timeout_halves_window(tmp_path):
    seen, slept, recovered = [], [], []

    def query(sql):
        a, b = data.window_of(sql)
        seen.append((a, b))
        if (b - a).days > 7:
            raise TimeoutError("read timed out")
        return [{"date": a.date().isoformat(), "act_symbol": "BRK.B", "iv_current": "0.3", "hv_current": "0.2"}]

    iv = data.fetch_implied_vol(["BRK-B"], tmp_path, query=query, start="2026-06-01", end="2026-06-28",
                                sleep=slept.append, on_recovered=lambda f, a: recovered.append((f, a)))
    assert set(iv.ticker) == {"BRK-B"} and iv.iv_current.dtype.kind == "f"
    assert any((b - a).days <= 7 for a, b in seen) and recovered
    assert "retried" in recovered[0][1] and any("halved" in action for _, action in recovered)
    assert slept
    assert "'BRK.B'" in data.iv_sql(["BRK-B"], pd.Timestamp("2026-06-01"), pd.Timestamp("2026-06-14"))


def test_earnings_cached_and_failures_empty(tmp_path):
    calls = []

    def get_dates(t):
        calls.append(t)
        if t == "BBB":
            raise RuntimeError("no data")
        return pd.DatetimeIndex(["2026-01-15", "2026-04-20"])

    e1 = data.fetch_earnings(["AAA", "BBB"], tmp_path, get_dates=get_dates)
    e2 = data.fetch_earnings(["AAA", "BBB"], tmp_path, get_dates=get_dates)
    assert e1["AAA"] == [pd.Timestamp("2026-01-15"), pd.Timestamp("2026-04-20")] and e1["BBB"] == []
    assert calls == ["AAA", "BBB"] and e2 == e1


def test_coverage_summary():
    df = walk(400)
    cov = data.coverage({"AAA": df}, ["BBB"], None, {"AAA": [pd.Timestamp("2025-01-15")], "CCC": []})
    assert cov["skipped"] == ["BBB"] and cov["tickers_without_earnings"] == ["CCC"]
    assert cov["rows_per_ticker_year"]["AAA"]["2024"] > 200 and cov["earnings_first_date"]["AAA"] == "2025-01-15"


def test_iv_fetch_resumes_from_partial_cache_and_retries_errors(tmp_path):
    import urllib.error
    calls = {"n": 0, "windows": []}

    def flaky(sql):
        a, b = data.window_of(sql)
        calls["n"] += 1
        calls["windows"].append(a)
        if calls["n"] == 2:
            raise urllib.error.URLError("connection reset")        # transient: retried
        if calls["n"] in (4, 5):
            raise RuntimeError("DoltHub: internal error")           # persists through the one retry
        return [{"date": a.date().isoformat(), "act_symbol": "AAPL", "iv_current": "0.3", "hv_current": "0.2"}]

    with pytest.raises(RuntimeError):
        data.fetch_implied_vol(["AAPL"], tmp_path, query=flaky, start="2026-01-01", end="2026-02-25", sleep=lambda s: None,
                               retries=1, workers=1)
    assert (tmp_path / "iv.partial.jsonl").exists()
    done_before = calls["n"]
    iv = data.fetch_implied_vol(["AAPL"], tmp_path, query=flaky, start="2026-01-01", end="2026-02-25", sleep=lambda s: None,
                                retries=1, workers=1)
    assert len(iv) == 4 and sorted(iv.date.dt.strftime("%Y-%m-%d")) == ["2026-01-01", "2026-01-15", "2026-01-29", "2026-02-12"]
    assert calls["n"] - done_before <= 3                              # only the windows not yet cached were fetched
    assert (tmp_path / "iv.csv").exists() and not (tmp_path / "iv.partial.jsonl").exists()
