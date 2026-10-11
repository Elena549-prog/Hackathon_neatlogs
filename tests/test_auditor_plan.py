"""AuditPlan validation (AUDITOR_SPEC section 5), freeze hash, what-tested line, universe groups (section 2)."""
import copy
import re

import pytest

from src.auditor import plan, universe

RAW = {
    "refuse": {"is_refused": False, "reason": ""},
    "family": "stock_long",
    "universe_group": "all_50",
    "conditions": [{"feature": "ret_5d", "op": "<", "value": -0.03},
                   {"feature": "close_to_ma200", "op": ">", "value": 1.0}],
    "exit": {"target_pct": 0.05, "stop_pct": 0.03, "horizon_days": 10},
    "hypothesis": "dips in an uptrend recover",
    "assumptions": ["'uptrend' read as close above its 200-day average"],
    "not_tested": [],
    "core_trigger_tested": True,
}


def raw(**over):
    r = copy.deepcopy(RAW)
    r.update(over)
    return r


def test_groups_partition_the_50():
    assert len(universe.ALL) == 50 == len(set(universe.ALL))
    sectors = ["tech", "financials", "healthcare", "energy", "consumer", "industrials"]
    seen = [t for g in sectors for t in universe.GROUPS[g]]
    assert len(seen) == 50 and set(seen) == set(universe.ALL)
    assert universe.GROUPS["all_50"] == universe.ALL
    assert len(universe.GROUPS["tech"]) == 17 and len(universe.GROUPS["mega_cap"]) == 10
    assert set(universe.GROUPS["mega_cap"]) <= set(universe.ALL)
    assert set(universe.GROUPS) == {"all_50", "tech", "financials", "healthcare", "energy", "consumer", "industrials", "mega_cap"}


def test_valid_stock_plan_converts_list_conditions():
    p, err = plan.validate(raw())
    assert err is None
    assert p["conditions"] == {"ret_5d": ["<", -0.03], "close_to_ma200": [">", 1.0]}
    assert p["exit"] == {"target_pct": 0.05, "stop_pct": 0.03, "horizon_days": 10}
    assert p["refused"] is False
    h = plan.plan_hash(p)
    assert re.fullmatch(r"[0-9a-f]{64}", h)
    reordered = {k: p[k] for k in reversed(list(p))}
    assert plan.plan_hash(reordered) == h


@pytest.mark.parametrize("over, needle", [
    ({"family": "crypto_long"}, "family"),
    ({"universe_group": ["AAPL", "MSFT"]}, "universe_group"),
    ({"universe_group": "faang"}, "universe_group"),
    ({"conditions": [{"feature": "ret_%dd" % k, "op": ">", "value": 0} for k in (1, 5, 10, 20)] + [{"feature": "vol_20d", "op": ">", "value": 0}]}, "4"),
    ({"conditions": [{"feature": "ret_5d", "op": "==", "value": 0}]}, "operator"),
    ({"conditions": [{"feature": "ret_5d", "op": "<", "value": "-0.03"}]}, "numeric"),
    ({"conditions": [{"feature": "ret_5d", "op": "<", "value": -0.03}, {"feature": "ret_5d", "op": ">", "value": -0.1}]}, "one condition per feature"),
    ({"conditions": [{"feature": "iv", "op": ">", "value": 0.3}]}, "implied"),
    ({"conditions": [{"feature": "momentum", "op": ">", "value": 0.3}]}, "feature"),
    ({"exit": {"target_pct": 0.25, "stop_pct": 0.03, "horizon_days": 10}}, "target"),
    ({"exit": {"target_pct": 0.05, "stop_pct": 0.005, "horizon_days": 10}}, "stop"),
    ({"exit": {"target_pct": 0.05, "stop_pct": 0.03, "horizon_days": 21}}, "horizon"),
    ({"exit": None}, "exit"),
    ({"not_tested": "news"}, "not_tested"),
    ({"core_trigger_tested": "yes"}, "core_trigger_tested"),
])
def test_rejects_invalid_plans(over, needle):
    p, err = plan.validate(raw(**over))
    assert p is None and needle in err


def test_straddle_ignores_exit_and_allows_iv():
    p, err = plan.validate(raw(family="straddle_sell", universe_group="mega_cap",
                               conditions=[{"feature": "iv_hv_ratio", "op": ">", "value": 1.2}]))
    assert err is None and "exit" not in p and p["conditions"] == {"iv_hv_ratio": [">", 1.2]}


def test_zero_conditions_allowed():
    p, err = plan.validate(raw(conditions=[]))
    assert err is None and p["conditions"] == {}


def test_refusal_passes_through():
    p, err = plan.validate(raw(refuse={"is_refused": True, "reason": "market manipulation"}, family="nonsense"))
    assert err is None and p["refused"] is True and p["reason"] == "market manipulation"


def test_what_tested_line():
    p, _ = plan.validate(raw())
    assert plan.what_tested(p) == ("stock_long on all_50 (50 tickers): enter when ret_5d < -0.03 and "
                                   "close_to_ma200 > 1.0; exit at +5% / -3% / 10 days. Not tested: nothing.")
    s, _ = plan.validate(raw(family="straddle_buy", universe_group="tech",
                             conditions=[{"feature": "earnings_within_10d", "op": ">=", "value": 1}],
                             not_tested=["news sentiment"]))
    assert plan.what_tested(s) == ("straddle_buy on tech (17 tickers): enter when earnings_within_10d >= 1; "
                                   "hold 10 days. Not tested: news sentiment.")
    e, _ = plan.validate(raw(conditions=[]))
    assert "enter every day" in plan.what_tested(e)
