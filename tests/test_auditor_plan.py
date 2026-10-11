"""Plan validation, conversion, freeze hash and the 'What was tested' line (spec section 5)."""
import hashlib

import pytest

from src.auditor.plan import canonical, normalize, plan_hash, to_map, validate, what_was_tested
from tests.auditor_helpers import plan_reply


def valid(**kw):
    return to_map(plan_reply(**kw))


def test_valid_plan_passes_and_converts_list_to_map():
    p = valid()
    assert validate(p) is None
    assert p["conditions"] == {"ret_5d": ["<", -0.02]}


@pytest.mark.parametrize("change, fragment", [
    ({"family": "covered_call"}, "family"),
    ({"universe_group": "faang"}, "universe_group"),
    ({"universe_group": ["AAPL", "MSFT"]}, "universe_group"),
    ({"exit": {"target_pct": 0.5, "stop_pct": 0.03, "horizon_days": 10}}, "target_pct"),
    ({"exit": {"target_pct": 0.05, "stop_pct": 0.0, "horizon_days": 10}}, "stop_pct"),
    ({"exit": {"target_pct": 0.05, "stop_pct": 0.03, "horizon_days": 30}}, "horizon_days"),
    ({"exit": None}, "exit"),
    ({"core_trigger_tested": "yes"}, "core_trigger_tested"),
    ({"not_tested": "news"}, "not_tested"),
    ({"hypothesis": " "}, "hypothesis"),
])
def test_invalid_fields_are_rejected(change, fragment):
    p = valid()
    p.update(change)
    err = validate(p)
    assert err and fragment in err


def test_five_conditions_rejected():
    conds = [{"feature": f, "op": ">", "value": 0} for f in ("ret_1d", "ret_5d", "ret_10d", "ret_20d", "vol_20d")]
    assert "conditions" in validate(valid(conditions=conds))


def test_bad_operator_and_non_numeric_value_rejected():
    assert "operator" in validate(valid(conditions=[{"feature": "ret_5d", "op": "==", "value": 0}]))
    assert "number" in validate(valid(conditions=[{"feature": "ret_5d", "op": "<", "value": "low"}]))
    assert "number" in validate(valid(conditions=[{"feature": "ret_5d", "op": "<", "value": True}]))


def test_unknown_feature_rejected():
    assert "unknown feature" in validate(valid(conditions=[{"feature": "sentiment", "op": ">", "value": 0}]))


def test_implied_vol_features_rejected_for_stock_long_only():
    iv = [{"feature": "iv_hv_ratio", "op": ">", "value": 1.2}]
    assert "straddles only" in validate(valid(conditions=iv))
    assert validate(valid(family="straddle_buy", conditions=iv)) is None


def test_repeated_feature_or_extra_keys_raise_on_conversion():
    with pytest.raises(ValueError):
        to_map(plan_reply(conditions=[{"feature": "ret_5d", "op": "<", "value": 0}] * 2))
    with pytest.raises(ValueError):
        to_map(plan_reply(conditions=[{"feature": "ret_5d", "op": "<", "value": 0, "note": "x"}]))


def test_refusal_is_valid_with_a_reason_and_ignores_other_fields():
    p = valid(refuse=True)
    p["family"] = "nonsense"
    assert validate(p) is None
    p["refuse"]["reason"] = ""
    assert "reason" in validate(p)


def test_straddles_ignore_exit():
    p = normalize(valid(family="straddle_sell"))
    assert p["exit"] is None


def test_hash_is_sha256_of_canonical_sorted_json():
    p = normalize(valid())
    text = canonical(p)
    assert text.startswith("{\"assumptions\"")                 # keys sorted
    assert plan_hash(p) == hashlib.sha256(text.encode()).hexdigest()
    q = dict(reversed(list(p.items())))
    assert plan_hash(q) == plan_hash(p)                          # key order does not matter


def test_what_was_tested_line_is_written_from_the_plan():
    p = normalize(valid(group="all_50", conditions=[{"feature": "ret_5d", "op": "<", "value": -0.03},
                                                    {"feature": "close_to_ma200", "op": ">", "value": 1.0}]))
    assert what_was_tested(p) == ("stock_long on all_50 (50 tickers): enter when close_to_ma200 > 1 and "
                                  "ret_5d < -0.03; exit at +5% / -3% / 10 days. Not tested: nothing.")
    s = normalize(valid(family="straddle_buy", group="tech", conditions=[]))
    s["not_tested"] = ["news sentiment"]
    assert what_was_tested(s).endswith("no conditions); hold the at-the-money straddle 10 trading days. "
                                       "Not tested: news sentiment.")
