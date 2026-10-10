"""Paper-trade simulator: same High/Low rule as the labels, any stop and target."""
import numpy as np
import pandas as pd

from src.labels import label_setup
from src.simulator import first_hit, simulate
from tests.helpers import make_market, set_bar


def path(n=15):
    c = np.full(n, 100.0)
    return c, c.copy(), c.copy()            # close, high, low


def test_target_first_is_a_win():
    close, high, low = path()
    high[3], low[6] = 105.0, 96.0
    assert first_hit(close, high, low, 0, 100.0, 97.0, 105.0, 10) == ("win", 105.0)


def test_stop_first_is_a_loss():
    close, high, low = path()
    low[2], high[5] = 97.0, 110.0
    assert first_hit(close, high, low, 0, 100.0, 97.0, 105.0, 10) == ("loss", 97.0)


def test_same_day_both_is_a_loss():
    close, high, low = path()
    high[4], low[4] = 106.0, 96.0
    assert first_hit(close, high, low, 0, 100.0, 97.0, 105.0, 10) == ("loss", 97.0)


def test_neither_expires_at_the_horizon_close():
    close, high, low = path()
    close[5] = 101.5
    assert first_hit(close, high, low, 0, 100.0, 97.0, 105.0, 5) == ("expired", 101.5)


def test_matches_the_label_rule_on_random_paths():
    rng = np.random.default_rng(7)
    for _ in range(300):
        adj = 100 * np.cumprod(1 + rng.normal(0, 0.02, 12))
        high, low = adj * (1 + rng.uniform(0, 0.03, 12)), adj * (1 - rng.uniform(0, 0.03, 12))
        df = pd.DataFrame({"Adj Close": adj, "Close": adj, "High": high, "Low": low},
                          index=pd.bdate_range("2025-01-01", periods=12))
        e = adj[0]
        outcome, _ = first_hit(adj, high, low, 0, e, e * 0.97, e * 1.05, 10)
        assert {"win": 1, "loss": 0, "expired": None}[outcome] == label_setup(df, 0)


def test_simulate_uses_the_plan_and_reports_pnl():
    m = make_market({"AAA": [100.0] * 20}, [])
    set_bar(m, "AAA", 4, high=104.0)
    plan = {"entry": 100.0, "stop": 98.0, "target": 103.0, "horizon_days": 5}
    out = simulate(plan, m, "AAA", m.prices["AAA"].index[0].date().isoformat())
    assert out["trade_outcome"] == "win"
    assert abs(out["pnl_pct"] - 0.03) < 1e-12
