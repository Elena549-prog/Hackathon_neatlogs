"""Report template (AUDITOR_SPEC section 9), prose check, registry."""
import json

from src.auditor import report
from src.auditor.checks import FIVE_PCT_LINE


def s(n=40, mean=0.01):
    return {"n": n, "blocks": 8, "win_rate": 0.5, "mean": mean, "median": mean, "ci_low": mean - 0.005,
            "ci_high": mean + 0.005, "worst_trade": -0.05, "worst_window": -0.1}


def ctx(**over):
    c = {"idea": "buy dips in an uptrend", "audit_id": "a1",
         "plan": {"refused": False, "family": "stock_long", "universe_group": "all_50",
                  "conditions": {"ret_5d": ["<", -0.03]}, "exit": {"target_pct": 0.05, "stop_pct": 0.03, "horizon_days": 10},
                  "hypothesis": "h", "assumptions": ["'dip' read as ret_5d < -3%"], "not_tested": [], "core_trigger_tested": True},
         "plan_hash": "ab" * 32, "what_tested": "stock_long on all_50 (50 tickers): enter when ret_5d < -0.03; exit at +5% / -3% / 10 days. Not tested: nothing.",
         "verdict": {"verdict": "promising", "reason": "all rules passed", "headline": {"n": 40, "mean": 0.01, "ci_low": 0.005, "paired_ci_low": 0.002}, "downgrades": []},
         "coverage": {"rows_per_ticker_year": {"AAPL": {"2015": 252}}, "skipped": [], "iv_rows": 0, "iv_range": None,
                      "earnings_first_date": {"AAPL": "2019-01-29"}, "tickers_without_earnings": []},
         "drops": {"train": {"exit_after_cutoff": 3, "exit_past_data": 0}, "validation": {"exit_after_cutoff": 0, "exit_past_data": 2}},
         "base": {"train": s(100, 0.02), "validation": s()}, "baseline": {"train": s(500, 0.001), "validation": s(200, 0.0), "paired_ci_low": 0.002},
         "random_baseline": {"train": s(100, 0.0), "validation": s(40, 0.0)}, "stricter": None,
         "tail": {"worst_trade": -0.05, "worst_window": -0.1, "fails": False},
         "checks": [{"check": "evidence", "passed": True, "value": {"n": 40, "blocks": 8}, "note": "ok"}],
         "followups": [], "window_count": 2, "critique": "The edge is thin.", "prose": None,
         "recoveries": [{"failed": "DoltHub timeout", "action": "halved the window", "injected": True}],
         "cost": {"calls": 3, "prompt_tokens": 3000, "completion_tokens": 400, "usd": 0.0123}, "trace_id": "trace-1",
         "small_group_note": None, "earnings_caveat": False, "fake_llm": False, "budget_hit": False}
    c.update(over)
    return c


def test_render_order_and_fixed_copy():
    md = report.render(ctx())
    heads = [l for l in md.splitlines() if l.startswith("## ")]
    assert [h.split(". ")[0] for h in heads] == ["## 1", "## 2", "## 3", "## 4", "## 5", "## 6", "## 7", "## 8", "## 9", "## 10"]
    assert md.startswith("# ") and "stock_long on all_50" in md.splitlines()[2]
    assert "PROMISING" in md and "Passed a 6-month historical screen. Not a forecast. Not financial advice." in md
    assert "ab" * 32 in md and FIVE_PCT_LINE in md and "2 audit" in md
    assert "INJECTED" in md and "REAL" not in md.split("## 8")[1].split("## 9")[0].replace("INJECTED", "")
    assert "$0.0123" in md and "trace-1" in md
    assert "Not financial advice" in md.split("## 10")[1] and "survivorship" in md.split("## 10")[1].lower()
    assert "FAKE LLM" not in md
    assert "FAKE LLM" in report.render(ctx(fake_llm=True))


def test_inconclusive_subtitle_and_small_group_and_caveats():
    md = report.render(ctx(verdict={"verdict": "inconclusive", "reason": "not enough evidence: validation n < 30", "headline": {"n": 12}, "downgrades": []},
                           small_group_note="energy has 2 tickers: usually inconclusive for lack of trades", earnings_caveat=True, budget_hit=True))
    assert "inconclusive: a strategy with no real edge lands here about half the time" in md
    assert "energy has 2 tickers" in md.split("## 4")[0]
    assert "announce dates weeks ahead" in md and "LLM call cap" in md


def test_prose_ok_bans_phrases():
    for bad in ("will profit", "Guaranteed", "RISK-FREE", "we recommend", "You should buy", "you should sell", "sure thing"):
        assert report.prose_ok("This %s next quarter." % bad) is False
    assert report.prose_ok("The validation mean is below zero, so the idea did not hold up.") is True


def test_registry_append_and_count(tmp_path):
    p = tmp_path / "registry.jsonl"
    assert report.registry_count(p) == 0
    report.append_registry(p, {"date": "2026-10-11", "idea": "x", "family": "stock_long", "universe_group": "all_50",
                               "plan_hash": "h", "verdict": "kill"})
    report.append_registry(p, {"date": "2026-10-11", "idea": "y", "family": "stock_long", "universe_group": "tech",
                               "plan_hash": "h2", "verdict": "inconclusive"})
    assert report.registry_count(p) == 2 and json.loads(p.read_text().splitlines()[1])["idea"] == "y"


def test_registry_count_excludes_fake_runs(tmp_path):
    p = tmp_path / "registry.jsonl"
    report.append_registry(p, {"date": "d", "idea": "x", "family": "stock_long", "universe_group": "all_50", "plan_hash": "h", "verdict": "kill", "provider": "fake"})
    report.append_registry(p, {"date": "d", "idea": "y", "family": "stock_long", "universe_group": "all_50", "plan_hash": "h", "verdict": "kill", "provider": "deepseek"})
    report.append_registry(p, {"date": "d", "idea": "z", "family": "stock_long", "universe_group": "all_50", "plan_hash": "h", "verdict": "kill"})
    assert report.registry_count(p) == 2
