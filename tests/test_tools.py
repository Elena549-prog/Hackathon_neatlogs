"""Swarm tools: get_prices and backtest never use information from after the decision date."""
import pytest

from src.tools import backtest, get_prices, wilson_low
from tests.helpers import make_market


def plan(**conditions):
    return {"conditions": conditions or {}, "horizon_days": 10}


def test_get_prices_returns_nothing_after_end_date():
    closes = [100.0] * 30
    closes[21] = 500.0                      # spike the day after end_date
    m = make_market({"AAA": closes}, [])
    end = m.prices["AAA"].index[20]
    out = get_prices(m, "AAA", end.date().isoformat(), lookback_days=50)
    assert out.index.max() == end
    assert out["Adj Close"].max() == 100.0


def test_get_prices_lookback():
    m = make_market({"AAA": [float(i) for i in range(1, 31)]}, [])
    out = get_prices(m, "AAA", m.prices["AAA"].index[19], lookback_days=5)
    assert list(out["Adj Close"]) == [16.0, 17.0, 18.0, 19.0, 20.0]


@pytest.mark.parametrize("wins, n, low", [(18, 40, 0.307), (135, 300, 0.395), (511, 1263, 0.378)])
def test_wilson_lower_bound_matches_the_spec_table(wins, n, low):
    assert wilson_low(wins, n) == pytest.approx(low, abs=0.0005)


def test_wilson_with_no_cases():
    assert wilson_low(0, 0) is None


def test_backtest_hand_values():
    setups = [("AAA", i, "train", int(i < 18)) for i in range(40)]
    m = make_market({"AAA": [100.0] * 80}, setups)
    out = backtest(plan(), m, m.prices["AAA"].index[70])
    assert (out["n"], out["eligible"], out["hit_rate"]) == (40, 40, 0.45)
    assert out["hit_rate_low"] == pytest.approx(0.307, abs=0.0005)


def test_backtest_only_counts_labels_known_before_the_decision():
    setups = [("AAA", i, "train", 1) for i in range(16)]
    m = make_market({"AAA": [100.0] * 40}, setups)
    out = backtest(plan(), m, m.prices["AAA"].index[15])
    assert out["n"] == out["eligible"] == 5   # rows 0..4: label known by row 14; row 5's label needs row 15


def test_backtest_filters_on_conditions():
    setups = [("AAA", 0, "train", 1, {"ret_5d": 0.10, "vol_20d": 0.01}),
              ("AAA", 1, "train", 0, {"ret_5d": 0.05, "vol_20d": 0.03}),
              ("AAA", 2, "train", 0, {"ret_5d": -0.10, "vol_20d": 0.01})]
    m = make_market({"AAA": [100.0] * 40}, setups)
    d = m.prices["AAA"].index[30]
    assert backtest(plan(ret_5d=[">", 0.0]), m, d)["n"] == 2
    assert backtest(plan(ret_5d=[">", 0.0], vol_20d=["<", 0.02]), m, d)["n"] == 1
    assert backtest(plan(ret_5d=[">=", 0.05]), m, d)["n"] == 2
    assert backtest(plan(ret_5d=["<=", -0.10]), m, d)["n"] == 1
    assert backtest(plan(), m, d)["n"] == 3
    assert backtest(plan(ret_5d=[">", 0.0]), m, d)["eligible"] == 3    # conditions don't change eligibility


def test_backtest_ignores_other_splits_and_refuses_them():
    m = make_market({"AAA": [100.0] * 40}, [("AAA", 0, "train", 1), ("AAA", 1, "validation", 1)])
    assert backtest(plan(), m, m.prices["AAA"].index[30])["n"] == 1
    with pytest.raises(ValueError):
        backtest(plan(), m, m.prices["AAA"].index[30], split="validation")


def test_backtest_with_no_cases():
    m = make_market({"AAA": [100.0] * 40}, [("AAA", 20, "train", 0)])
    out = backtest(plan(), m, m.prices["AAA"].index[25])
    assert (out["n"], out["hit_rate"], out["hit_rate_low"]) == (0, None, None)
