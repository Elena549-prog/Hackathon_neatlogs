"""Verdict rules (AUDITOR_SPEC section 7), each branch on hand-made statistics."""
import pytest

from src.auditor import verdict


def s(n=100, blocks=20, mean=0.01, ci_low=0.002):
    return {"n": n, "blocks": blocks, "win_rate": 0.5, "mean": mean, "median": mean, "ci_low": ci_low,
            "ci_high": mean + 0.01, "worst_trade": -0.05, "worst_window": -0.1}


def results(**over):
    r = {"plan": {"refused": False, "family": "stock_long", "core_trigger_tested": True},
         "base": {"train": s(mean=0.02), "validation": s(n=40, blocks=8, mean=0.01, ci_low=0.002)},
         "baseline": {"train": s(mean=0.001), "validation": s(mean=0.0), "paired_ci_low": 0.001},
         "stricter": None, "tail": {"worst_trade": -0.05, "worst_window": -0.1, "fails": False},
         "followup_downgrades": []}
    r.update(over)
    return r


def test_cannot_audit_refused():
    v = verdict.decide(results(plan={"refused": True, "reason": "market manipulation"}))
    assert v["verdict"] == "cannot_audit" and v["reason"] == "refused" and v["headline"] == {}


def test_cannot_audit_invalid_twice():
    v = verdict.decide(results(plan={"refused": False, "invalid_twice": True}))
    assert v["verdict"] == "cannot_audit" and v["reason"] == "no valid plan"


def test_cannot_audit_core_trigger():
    v = verdict.decide(results(plan={"refused": False, "family": "stock_long", "core_trigger_tested": False}))
    assert v["verdict"] == "cannot_audit" and v["reason"] == "core of the idea not testable with available data"


def test_inconclusive_n_below_30():
    r = results()
    r["base"]["validation"] = s(n=29, blocks=8, mean=0.01)
    v = verdict.decide(r)
    assert v["verdict"] == "inconclusive" and "n < 30" in v["reason"] and v["headline"]["n"] == 29


def test_inconclusive_fewer_than_6_blocks():
    r = results()
    r["base"]["validation"] = s(n=40, blocks=5, mean=0.01)
    assert "blocks" in verdict.decide(r)["reason"] and verdict.decide(r)["verdict"] == "inconclusive"


def test_kill_on_nonpositive_mean():
    r = results()
    r["base"]["validation"] = s(n=40, blocks=8, mean=0.0, ci_low=-0.01)
    v = verdict.decide(r)
    assert v["verdict"] == "kill" and v["reason"] == "validation mean <= 0 with enough evidence"


def test_promising_all_rules():
    v = verdict.decide(results())
    assert v["verdict"] == "promising" and v["downgrades"] == []
    assert v["headline"] == {"n": 40, "mean": 0.01, "ci_low": 0.002, "paired_ci_low": 0.001}


def test_inconclusive_lower_bound_not_positive():
    r = results()
    r["base"]["validation"] = s(n=40, blocks=8, mean=0.01, ci_low=-0.001)
    v = verdict.decide(r)
    assert v["verdict"] == "inconclusive" and "lower bound" in v["reason"]


def test_inconclusive_failing_paired_baseline():
    r = results()
    r["baseline"]["paired_ci_low"] = -0.001
    assert verdict.decide(r)["verdict"] == "inconclusive" and "baseline" in verdict.decide(r)["reason"]


def test_inconclusive_train_not_above_baseline():
    r = results()
    r["baseline"]["train"] = s(mean=0.03)
    assert verdict.decide(r)["verdict"] == "inconclusive"


def test_inconclusive_failing_stricter_cost():
    r = results(plan={"refused": False, "family": "straddle_buy", "core_trigger_tested": True},
                stricter={"validation": s(n=40, blocks=8, mean=0.005, ci_low=-0.001)})
    assert verdict.decide(r)["verdict"] == "inconclusive" and "stricter" in verdict.decide(r)["reason"]


def test_inconclusive_tail_risk_downgrade():
    r = results(plan={"refused": False, "family": "straddle_sell", "core_trigger_tested": True},
                stricter={"validation": s(n=40, blocks=8, mean=0.005, ci_low=0.001)},
                tail={"worst_trade": -0.6, "worst_window": -0.9, "fails": True, "worst_trade_premiums": -6.0})
    v = verdict.decide(r)
    assert v["verdict"] == "inconclusive" and v["downgrades"] == [{"cause": "tail risk", "from": "promising", "to": "inconclusive"}]


def test_followup_downgrade_applies():
    v = verdict.decide(results(followup_downgrades=[{"cause": "F4: validation mean <= 0 without the top ticker"}]))
    assert v["verdict"] == "inconclusive" and v["downgrades"][0]["cause"].startswith("F4")
