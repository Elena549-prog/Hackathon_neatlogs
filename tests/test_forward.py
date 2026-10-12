import pandas as pd
import pytest

from src.forward import forward_setups, position
from tests.helpers import make_market, set_bar

PLAN = {"entry": 100.0, "stop": 97.0, "target": 105.0, "horizon_days": 10}


@pytest.mark.parametrize("n_rows, bar, status, outcome, pnl, days", [
    (60, ("high", 33, 105.0), "closed", "win", 0.05, 10),        # target hit on day 3
    (60, ("low", 32, 97.0), "closed", "loss", -0.03, 10),        # stop hit on day 2
    (60, None, "closed", "expired", 0.0, 10),                    # 10 days, neither hit
    (35, None, "open", None, 0.0, 4),                            # only 4 days of data after entry
    (31, None, "open", None, 0.0, 0),                            # decided on the last close
])
def test_position_is_closed_by_the_first_hit_or_open_until_the_horizon(n_rows, bar, status, outcome, pnl, days):
    m = make_market({"AAA": [100.0] * n_rows}, [("AAA", 30, "train", 1)])
    if bar:
        set_bar(m, "AAA", bar[1], **{bar[0]: bar[2]})
    p = position(PLAN, m, "AAA", m.setups["date"][0])
    assert (p["status"], p["trade_outcome"], p["days_held"]) == (status, outcome, days)
    assert p["pnl_pct"] == pytest.approx(pnl)


def test_open_position_is_marked_at_the_last_close():
    closes = [100.0] * 34 + [102.0]
    m = make_market({"AAA": closes}, [("AAA", 30, "train", 1)])
    p = position(PLAN, m, "AAA", m.setups["date"][0])
    assert p["status"] == "open" and p["pnl_pct"] == pytest.approx(0.02)
    assert p["as_of"] == m.prices["AAA"].index[-1].date().isoformat()


def test_forward_setups_start_after_the_cutoff_and_need_full_history():
    dates = pd.bdate_range("2025-01-01", periods=260, name="Date")
    raw = pd.DataFrame({"Adj Close": [100.0 + i for i in range(260)]}, index=dates)
    rows = forward_setups({"AAA": raw}, after=dates[250].date().isoformat())
    assert [r["date"] for r in rows] == [d.date().isoformat() for d in dates[251:]]
    assert all(r["split"] == "forward" and r["label"] is None for r in rows)
    early = forward_setups({"AAA": raw}, after=dates[100].date().isoformat())   # no 200-day average yet
    assert early[0]["date"] == dates[199].date().isoformat()
