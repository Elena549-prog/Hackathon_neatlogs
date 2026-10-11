"""Follow-ups F1-F4 on hand-made trades (AUDITOR_SPEC sections 4, 12)."""
import pandas as pd

from src.auditor import backtest, followups as fu

CAL = pd.bdate_range("2024-01-01", "2026-07-29")


def prices_for(*tickers):
    return {t: pd.DataFrame({"Close": 1.0}, index=CAL) for t in tickers}


def trades(rows):
    """rows: (ticker, entry calendar position, ret)."""
    return pd.DataFrame([{"ticker": t, "entry_date": CAL[p], "ret": r} for t, p, r in rows], columns=["ticker", "entry_date", "ret"])


def split(train_rows, val_rows):
    return {"train": trades(train_rows), "validation": trades(val_rows)}


STOCK = {"family": "stock_long", "exit": {"target_pct": 0.05, "stop_pct": 0.03, "horizon_days": 3}}
STRADDLE = {"family": "straddle_buy"}


def test_choose_caps_at_three_and_filters():
    asked = [{"id": f, "reason": "r"} for f in ("F3", "F1", "f1", "F9", "F2", "F4")]
    chosen, ignored = fu.choose(asked, "straddle_sell")
    assert [c["id"] for c in chosen] == ["F1", "F2", "F4"]
    assert {"id": "F3", "why": "not run for straddle_sell"} in ignored and {"id": "F9", "why": "not on the follow-up menu"} in ignored
    chosen, ignored = fu.choose(asked, "stock_long")
    assert [c["id"] for c in chosen] == ["F3", "F1", "F2"] and {"id": "F4", "why": "at most 3 follow-ups per audit"} in ignored
    assert fu.choose(None, "stock_long") == ([], [])


def test_f1_uses_the_trades_own_holding_window():
    day = CAL.get_loc(pd.Timestamp("2026-02-02"))
    earnings = {"AAA": [CAL[day + 3]], "BBB": [], "CCC": [CAL[day + 8]]}
    t = split([], [("AAA", day, 0.10), ("BBB", day, 0.10), ("CCC", day, -0.02)])
    r = fu.f1_earnings_excluded(t, STOCK, prices_for("AAA", "BBB", "CCC"), earnings, CAL)
    # stock_long horizon 3: AAA's report on day+3 is inside, CCC's on day+8 is outside; BBB has no coverage
    assert r["validation"]["n"] == 1 and r["validation"]["mean"] == -0.02 and r["downgrade"] is True
    assert r["left_out"]["validation"] == {"earnings_in_window": 1, "no_earnings_coverage": 1}
    assert r["cause"].startswith("F1 earnings excluded")
    r = fu.f1_earnings_excluded(t, STRADDLE, prices_for("AAA", "BBB", "CCC"), earnings, CAL)
    assert r["validation"]["n"] == 0 and r["left_out"]["validation"]["earnings_in_window"] == 2    # 10 days: CCC too
    assert r["downgrade"] is False and "cannot be evaluated" in r["result"]       # no trades left: no mean to judge


def test_f1_report_day_itself_is_outside_the_window_and_missing_data_skips():
    day = CAL.get_loc(pd.Timestamp("2026-03-02"))
    t = split([], [("AAA", day, 0.05)])
    r = fu.f1_earnings_excluded(t, STOCK, prices_for("AAA"), {"AAA": [CAL[day]]}, CAL)
    assert r["validation"]["n"] == 1 and r["downgrade"] is False
    r = fu.f1_earnings_excluded(t, STOCK, prices_for("AAA"), {"AAA": []}, CAL)
    assert r.get("skipped") and r["downgrade"] is False


def years(signs):
    """One train trade per year starting 2015 on a synthetic calendar with the given return signs."""
    cal = pd.bdate_range("2015-01-01", "2026-07-29")
    rows = [{"ticker": "AAA", "entry_date": pd.Timestamp("%d-03-02" % (2015 + i)), "ret": 0.01 * s} for i, s in enumerate(signs)]
    return {"train": pd.DataFrame(rows), "validation": pd.DataFrame(columns=["ticker", "entry_date", "ret"])}, cal


def base(val_mean):
    return {"train": {"n": 1, "mean": 0.0}, "validation": {"n": 40, "mean": val_mean}}


def test_f2_more_than_half_the_years_opposite():
    t, cal = years([-1, -1, -1, 1])
    r = fu.f2_per_year(t, base(0.01), cal)
    assert r["downgrade"] is True and r["opposite_years"] == 3 and set(r["per_year"]) == {"2015", "2016", "2017", "2018"}
    t, cal = years([-1, -1, 1, 1])
    assert fu.f2_per_year(t, base(0.01), cal)["downgrade"] is False            # exactly half is not more than half


def test_f3_horizons_and_straddle_skip(monkeypatch):
    seen = []

    def fake_backtest(prices, features, plan, earnings, split):
        h = plan["exit"]["horizon_days"]
        seen.append(h)
        ret = 0.01 if h == 20 else -0.01
        return trades([("AAA", 600, ret)] if split == "validation" else [("AAA", 100, ret)]), {}

    monkeypatch.setattr(backtest, "run_backtest", fake_backtest)
    r = fu.f3_horizons(STOCK, {}, None, {}, CAL)
    assert sorted(set(seen)) == [5, 20] and r["downgrade"] is False and set(r["variants"]) == {"5", "20"}
    assert r["validation"]["mean"] == -0.01                                    # train/validation are the 5-day run
    monkeypatch.setattr(backtest, "run_backtest", lambda *a, **k: (trades([("AAA", 600, -0.01)]), {}))
    assert fu.f3_horizons(STOCK, {}, None, {}, CAL)["downgrade"] is True
    assert fu.f3_horizons(STRADDLE, {}, None, {}, CAL)["skipped"] is True


def test_f4_drops_the_top_contributor():
    day = CAL.get_loc(pd.Timestamp("2026-02-02"))
    t = split([("AAA", 10, 0.01)], [("AAA", day, 0.30), ("AAA", day + 20, 0.10), ("BBB", day, -0.01), ("CCC", day, 0.0)])
    r = fu.f4_concentration(t, CAL)
    assert r["ticker"] == "AAA" and r["validation"]["n"] == 2 and r["downgrade"] is True
    assert r["train"]["n"] == 0 and "AAA" not in r["result"]                    # tickers stay out of the Naysayer's text
    t = split([], [("AAA", day, 0.30), ("BBB", day, 0.02)])
    assert fu.f4_concentration(t, CAL)["downgrade"] is False
