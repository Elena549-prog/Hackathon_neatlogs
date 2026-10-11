"""Statistics, verdict rules, tail risk and follow-ups (spec sections 4, 7, 12)."""
import numpy as np
import pandas as pd
import pytest

from src.auditor import checks, verdict as rules


# ------------------------------------------------------------------------------- statistics

def test_bootstrap_mean_hand_example():
    # block 0: two trades of +10%; block 1: one trade of -10%. Possible resample means:
    # (0,0) +10%, (0,1) +3.3%, (1,1) -10%, so the 2.5th/97.5th percentiles are -10% and +10%.
    lo, hi = checks.bootstrap_mean([0, 0, 1], [0.1, 0.1, -0.1])
    assert lo == pytest.approx(-0.1) and hi == pytest.approx(0.1)


def test_bootstrap_mean_single_block_is_the_mean():
    lo, hi = checks.bootstrap_mean([3, 3], [0.02, 0.04])
    assert lo == pytest.approx(0.03) and hi == pytest.approx(0.03)


def test_paired_lower_bound_identical_sets_is_zero_and_shift_is_found():
    b, r = [0, 1, 2, 3], [0.01, -0.02, 0.03, 0.0]
    assert checks.paired_lower_bound(b, r, b, r) == pytest.approx(0.0)
    assert checks.paired_lower_bound(b, [x + 0.05 for x in r], b, r) == pytest.approx(0.05)


def test_worst_window_sums_entries_within_10_trading_days():
    cal = pd.bdate_range("2026-01-01", periods=40)
    dates = [cal[0], cal[5], cal[20]]
    assert checks.worst_window(dates, [-0.1, -0.2, -0.05], cal) == pytest.approx(-0.3)


def make_stats(n=40, blocks=8, mean=0.01, ci_low=0.002, train_mean=0.01):
    s = {"n": n, "blocks": blocks, "win_rate": 0.5, "mean": mean, "median": mean, "ci_low": ci_low,
         "ci_high": 0.02, "worst_trade": -0.05, "worst_window": -0.1}
    return {"train": dict(s, mean=train_mean), "validation": s}


BASELINE = make_stats(mean=0.0, ci_low=-0.01, train_mean=0.0)


# ---------------------------------------------------------------------------------- verdict

def test_inconclusive_when_too_few_trades_or_blocks():
    assert rules.decide("stock_long", make_stats(n=29), BASELINE, 0.01)["verdict"] == "inconclusive"
    assert rules.decide("stock_long", make_stats(blocks=5), BASELINE, 0.01)["verdict"] == "inconclusive"


def test_kill_when_enough_evidence_and_mean_not_positive():
    assert rules.decide("stock_long", make_stats(mean=0.0), BASELINE, 0.01)["verdict"] == "kill"
    assert rules.decide("stock_long", make_stats(mean=-0.01), BASELINE, 0.01)["verdict"] == "kill"


def test_thin_evidence_never_becomes_kill():
    v = rules.decide("stock_long", make_stats(n=10, mean=-0.05), BASELINE, -0.1)
    assert v["verdict"] == "inconclusive"


def test_promising_when_every_rule_holds():
    assert rules.decide("stock_long", make_stats(), BASELINE, 0.004)["verdict"] == "promising"


@pytest.mark.parametrize("kw, paired", [({"ci_low": -0.001}, 0.004), ({}, -0.001), ({"train_mean": -0.01}, 0.004)])
def test_inconclusive_when_a_promising_rule_fails(kw, paired):
    assert rules.decide("stock_long", make_stats(**kw), BASELINE, paired)["verdict"] == "inconclusive"


def test_failing_the_paired_baseline_test():
    v = rules.decide("stock_long", make_stats(), BASELINE, 0.0)
    assert v["verdict"] == "inconclusive" and "baseline" in v["reason"]


def test_straddles_need_the_stricter_cost_check():
    good, bad = make_stats(), make_stats(ci_low=-0.01)
    assert rules.decide("straddle_buy", make_stats(), BASELINE, 0.004, stricter=good)["verdict"] == "promising"
    v = rules.decide("straddle_buy", make_stats(), BASELINE, 0.004, stricter=bad)
    assert v["verdict"] == "inconclusive" and "stricter-cost" in v["reason"]


def test_tail_risk_downgrades_promising():
    v = rules.decide("straddle_sell", make_stats(), BASELINE, 0.004, stricter=make_stats(),
                     tail={"downgrade": True, "reasons": ["worst trade 7 premiums"]})
    assert v["verdict"] == "inconclusive" and v["downgrades"][0]["cause"] == "tail risk"


# ------------------------------------------------------------------------------- tail risk

def sell_trades(rets, premiums, payoffs, splits, start="2025-06-02"):
    dates = pd.bdate_range(start, periods=len(rets))
    return pd.DataFrame({"ticker": "X", "date": dates, "ret": rets, "premium": premiums, "payoff": payoffs,
                         "split": splits})


def test_sell_tail_rule_worst_trade_over_5_premiums():
    cal = pd.bdate_range("2025-01-01", periods=400)
    prem = 0.02
    payoffs = [0.0] * 9 + [0.13]                                 # loss 0.11 = 5.5 premiums
    rets = [(prem - p) / prem for p in payoffs]
    t = sell_trades(rets, [prem] * 10, payoffs, ["validation"] * 10)
    tr = checks.tail_risk("straddle_sell", t, cal)
    assert tr["worst_loss_premiums"] == pytest.approx(5.5) and tr["downgrade"]


def test_sell_tail_rule_worst_window_over_total_validation_gain():
    cal = pd.bdate_range("2024-01-01", "2026-12-31")
    prem = 0.02

    def trades(val_payoff):
        # train: two losses two days apart (returns -1.5 and -0.5: one window of -2.0, each under 5 premiums)
        # validation: three trades with the given payoff
        dates = [pd.Timestamp("2025-03-03"), pd.Timestamp("2025-03-05")] + list(
            pd.bdate_range("2026-01-05", periods=3, freq="20B"))
        pays = [0.05, 0.03] + [val_payoff] * 3
        return pd.DataFrame({"ticker": "X", "date": dates, "premium": prem, "payoff": pays,
                             "ret": [(prem - p) / prem for p in pays],
                             "split": ["train", "train", "validation", "validation", "validation"]})

    big_gain = checks.tail_risk("straddle_sell", trades(0.0), cal)      # validation gain 3 x 1.0 = 3.0
    assert big_gain["worst_window"] == pytest.approx(-2.0) and not big_gain["downgrade"]
    small_gain = checks.tail_risk("straddle_sell", trades(0.018), cal)  # validation gain 3 x 0.1 = 0.3
    assert small_gain["downgrade"] and "window" in small_gain["reasons"][0]


def test_other_families_report_tail_without_downgrade():
    t = sell_trades([-0.9, 0.1], [np.nan] * 2, [np.nan] * 2, ["validation"] * 2)
    tr = checks.tail_risk("stock_long", t, pd.bdate_range("2025-01-01", periods=400))
    assert tr["worst_trade"] == pytest.approx(-0.9) and not tr["downgrade"]


# ------------------------------------------------------------------------------- follow-ups

def test_pick_followups_caps_at_three_and_skips_f3_for_straddles():
    asked = [{"id": i, "reason": "r"} for i in ("F1", "F2", "F3", "F4")]
    assert [f["id"] for f in checks.pick_followups(asked, "stock_long")] == ["F1", "F2", "F3"]
    assert [f["id"] for f in checks.pick_followups(asked, "straddle_buy")] == ["F1", "F2", "F4"]
    assert checks.pick_followups([{"id": "F9"}, {"id": "F1"}, {"id": "F1"}], "stock_long") == [{"id": "F1", "reason": ""}]


def test_followups_only_downgrade_promising():
    bad_f = [{"id": "F4", "downgrade": True, "note": "without NVDA the mean is -0.1%"}]
    assert rules.decide("stock_long", make_stats(), BASELINE, 0.004, followups=bad_f)["verdict"] == "inconclusive"
    assert rules.decide("stock_long", make_stats(mean=-0.01), BASELINE, 0.004, followups=bad_f)["verdict"] == "kill"
    thin = rules.decide("stock_long", make_stats(n=5), BASELINE, 0.004, followups=bad_f)
    assert thin["verdict"] == "inconclusive" and thin["downgrades"] == []


def test_f2_counts_opposite_sign_years():
    dates = pd.to_datetime(["2016-03-01", "2017-03-01", "2018-03-01"])
    trades = pd.DataFrame({"ticker": "X", "date": dates, "split": "train", "ret": [-0.01, -0.02, 0.03]})
    r = checks.run_followup("F2", None, {"family": "stock_long"}, trades,
                            {"validation": {"mean": 0.01}}, None)
    assert r["result"]["opposite_sign_years"] == 2 and r["downgrade"]
