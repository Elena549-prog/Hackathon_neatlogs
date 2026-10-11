"""Statistics and coded checks (AUDITOR_SPEC section 7) on hand-made trades."""
import numpy as np
import pandas as pd
import pytest

from src.auditor import checks

CAL = pd.bdate_range("2025-01-02", periods=1200)


def trades(rets, start=0, step=1, ticker="AAA"):
    dates = [CAL[start + i * step] for i in range(len(rets))]
    return pd.DataFrame({"ticker": ticker, "entry_date": dates, "exit_date": dates, "entry": 100.0,
                         "exit": [100 * (1 + r) for r in rets], "ret": list(rets)})


def test_block_ids_every_ten_trading_days():
    ids = checks.block_ids(pd.Series([CAL[0], CAL[9], CAL[10], CAL[25]]), CAL)
    assert list(ids) == [0, 0, 1, 2]


def test_bootstrap_mean_hand_example():
    rets = [0.02, -0.01] * 10
    t = trades(rets, step=2)                                   # 20 trades over 4 blocks
    lo, hi = checks.bootstrap_mean(t.entry_date, t.ret, CAL, seed=0)
    mean = float(np.mean(rets))
    assert lo <= mean <= hi and lo < hi
    assert checks.bootstrap_mean(t.entry_date, t.ret, CAL, seed=0) == (lo, hi)


def test_bootstrap_single_block_and_empty():
    t = trades([0.01, 0.03, 0.02])
    assert checks.bootstrap_mean(t.entry_date, t.ret, CAL) == (0.02, 0.02)
    lo, hi = checks.bootstrap_mean(pd.Series([], dtype="datetime64[ns]"), pd.Series([], dtype=float), CAL)
    assert np.isnan(lo) and np.isnan(hi)


def test_paired_lower_bound_sign():
    a = trades([0.02, -0.01] * 10, step=2)
    assert abs(checks.paired_lower_bound(a.entry_date, a.ret, a.entry_date, a.ret, CAL)) < 1e-12
    b = a.assign(ret=a.ret - 0.01)
    assert abs(checks.paired_lower_bound(a.entry_date, a.ret, b.entry_date, b.ret, CAL) - 0.01) < 1e-9


def test_stats_fields_and_worst_window():
    t = trades([0.05, -0.02, -0.03, 0.01, -0.04], start=0, step=3)   # entries on days 0,3,6,9,12
    s = checks.stats(t, CAL)
    assert set(s) == {"n", "blocks", "win_rate", "mean", "median", "ci_low", "ci_high", "worst_trade", "worst_window"}
    assert s["n"] == 5 and s["blocks"] == 2 and abs(s["win_rate"] - 0.4) < 1e-12
    assert abs(s["worst_trade"] + 0.04) < 1e-12
    assert abs(s["worst_window"] + 0.08) < 1e-12                     # days 3..12: -0.02-0.03+0.01-0.04
    e = checks.stats(t.iloc[:0], CAL)
    assert e["n"] == 0 and e["mean"] == 0 and e["blocks"] == 0


def test_equity_curve_downsample():
    t = trades([0.001] * 1000)
    curve = checks.equity_curve(t)
    assert len(curve) == 300 and abs(curve[-1][1] - 1.0) < 1e-9 and curve[0][0] == CAL[0].date().isoformat()
    short = checks.equity_curve(trades([0.1, -0.05]))
    assert short == [[CAL[0].date().isoformat(), 0.1], [CAL[1].date().isoformat(), 0.05]]
    assert checks.equity_curve(t.iloc[:0]) == []


def test_histogram_bins():
    rets = pd.Series(np.linspace(-0.2, 0.2, 200))
    h = checks.histogram(rets)
    assert len(h["edges"]) == 21 and len(h["counts"]) == 22 and sum(h["counts"]) == 200
    assert h["counts"][0] >= 1 and h["counts"][-1] >= 1
    assert checks.histogram(pd.Series([], dtype=float)) == {"edges": [], "counts": []}


def test_tail_risk_sell_rules():
    # seller returns are in premium units: -6 means the payoff was 7 premiums (loss of 6 premiums)
    base = trades([0.1, 0.1, -6.0, 0.1], step=3).assign(premium=0.1)
    fail_trade = checks.tail_risk(base, "straddle_sell", validation_total_gain=50.0)
    assert fail_trade["worst_trade_premiums"] < -5 and fail_trade["fails"] is True
    assert abs(fail_trade["worst_trade_pct"] + 0.6) < 1e-12                  # -6 premiums x 10% of price
    ok = checks.tail_risk(trades([0.1, -0.2], step=3).assign(premium=0.1), "straddle_sell", validation_total_gain=5.0)
    assert ok["fails"] is False and abs(ok["worst_trade_premiums"] + 0.2) < 1e-12
    window = checks.tail_risk(trades([-0.2, -0.2, -0.2], step=1).assign(premium=0.1), "straddle_sell", validation_total_gain=0.4)
    assert window["fails"] is True and abs(window["worst_window"] + 0.6) < 1e-12
    stock = checks.tail_risk(trades([-0.9]), "stock_long", validation_total_gain=0.0)
    assert stock["fails"] is False and "worst_trade_premiums" not in stock


def results(n_val=40, blocks=8, val_mean=0.01, train_mean=0.02, registry=0):
    s = lambda n, b, m: {"n": n, "blocks": b, "win_rate": 0.5, "mean": m, "median": m, "ci_low": m - 0.01,
                         "ci_high": m + 0.01, "worst_trade": -0.05, "worst_window": -0.1}
    return {"plan": {"family": "stock_long"}, "base": {"train": s(100, 20, train_mean), "validation": s(n_val, blocks, val_mean)},
            "baseline": {"train": s(500, 50, 0.001), "validation": s(200, 12, 0.0), "paired_ci_low": 0.002},
            "stricter": None, "tail": {"worst_trade": -0.05, "worst_window": -0.1, "fails": False},
            "drops": {"train": {"exit_after_cutoff": 3, "exit_past_data": 0}, "validation": {"exit_after_cutoff": 0, "exit_past_data": 2}},
            "dates_max": pd.Timestamp("2026-06-30")}


def test_coded_checks_evidence_and_decay():
    ok = checks.coded_checks(results(), registry_count=3)
    by = {c["check"]: c for c in ok}
    assert len(ok) == 7 and by["evidence"]["passed"] is True and by["shared_window"]["value"] == 3
    weak = {c["check"]: c for c in checks.coded_checks(results(n_val=29), registry_count=0)}
    assert weak["evidence"]["passed"] is False
    few = {c["check"]: c for c in checks.coded_checks(results(blocks=5), registry_count=0)}
    assert few["evidence"]["passed"] is False
    decay = {c["check"]: c for c in checks.coded_checks(results(val_mean=-0.01, train_mean=0.02), registry_count=0)}
    assert decay["decay"]["passed"] is False and "train" in decay["decay"]["note"]
    assert by["data_drops"]["value"]["train"]["exit_after_cutoff"] == 3


def test_leakage_raises():
    with pytest.raises(checks.LeakageError):
        checks.assert_no_leakage(pd.Series([pd.Timestamp("2026-06-30"), pd.Timestamp("2026-07-01")]))
    checks.assert_no_leakage(pd.Series([pd.Timestamp("2026-06-30")]))
