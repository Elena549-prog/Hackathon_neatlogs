"""Auditor agents (prompts, LLM calls) and the keyword fake LLM used for tests and development runs."""
import json
import re

from src.auditor import agents, plan, universe
from src.auditor.fake_llm import FAKE_PREFIX, make_fake_llm
from src.tracing import Tracer

DEMO = ["buy dips in an uptrend", "buy straddles on tech before earnings", "sell straddles on low-volatility mega-caps"]


def test_fake_planner_reads_keywords():
    llm = make_fake_llm(Tracer())
    raws = [agents.run_planner(llm, idea, None) for idea in DEMO]
    plans = [plan.validate(r) for r in raws]
    assert all(err is None for _, err in plans)
    p0, p1, p2 = (p for p, _ in plans)
    assert (p0["family"], p0["universe_group"]) == ("stock_long", "all_50")
    assert p0["conditions"] == {"ret_5d": ["<", -0.03], "close_to_ma200": [">", 1.0]}
    assert (p1["family"], p1["universe_group"], p1["conditions"]) == ("straddle_buy", "tech", {"earnings_within_10d": [">=", 1]})
    assert (p2["family"], p2["universe_group"]) == ("straddle_sell", "mega_cap") and "vol_20d" in p2["conditions"]
    assert all(p["assumptions"] for p in (p0, p1, p2))


def test_fake_refuses_and_untestable():
    llm = make_fake_llm(Tracer())
    refused, _ = plan.validate(agents.run_planner(llm, "pump the stock with coordinated buying", None))
    assert refused["refused"] is True
    untestable, err = plan.validate(agents.run_planner(llm, "buy when twitter sentiment turns positive", None))
    assert err is None and untestable["core_trigger_tested"] is False and untestable["not_tested"]


def test_fake_records_spans_and_prefix():
    tracer = Tracer()
    llm = make_fake_llm(tracer)
    agents.run_planner(llm, "buy dips in an uptrend", None)
    out = agents.run_naysayer(llm, {"what_tested": "x", "base": {}, "baseline": {}, "stricter": None, "tail": {}, "checks": []})
    prose = agents.run_reporter(llm, "# report")
    assert len(tracer.spans) == 3 and all(s["kind"] == "llm" and s["cost"] > 0 for s in tracer.spans)
    assert out["critique"].startswith(FAKE_PREFIX) and isinstance(out["doubts"], list)
    assert prose.startswith(FAKE_PREFIX)


def test_run_planner_passes_fix_reason():
    prompts = []

    def llm(agent, system, prompt, schema, **tags):
        prompts.append((agent, prompt, tags))
        return {"refuse": {"is_refused": False, "reason": ""}, "family": "stock_long", "universe_group": "all_50",
                "conditions": [], "exit": {"target_pct": 0.05, "stop_pct": 0.03, "horizon_days": 10}, "hypothesis": "h",
                "assumptions": [], "not_tested": [], "core_trigger_tested": True}

    agents.run_planner(llm, "idea", None)
    agents.run_planner(llm, "idea", "exit target_pct must be between 0.01 and 0.2")
    assert prompts[0][0] == "planner" and "target_pct must be" not in prompts[0][1]
    assert "target_pct must be" in prompts[1][1] and prompts[1][2]["step"] == "plan"
    assert json.dumps(plan.SCHEMA) and "universe_group" in agents.PLANNER_SYSTEM and "refuse" in agents.PLANNER_SYSTEM.lower()


def test_naysayer_context_has_no_tickers_or_dates():
    results = {"what_tested": "stock_long on all_50 (50 tickers): enter every day; exit at +5% / -3% / 10 days. Not tested: nothing.",
               "base": {"train": {"n": 1, "mean": 0.0}, "validation": {"n": 1, "mean": 0.0}},
               "baseline": {"train": {"n": 1, "mean": 0.0}, "validation": {"n": 1, "mean": 0.0}, "paired_ci_low": 0.0},
               "stricter": None, "tail": {"worst_trade": -0.1, "worst_window": -0.2, "fails": False},
               "checks": [{"check": "leakage", "passed": True, "value": "2026-06-30", "note": "no date after 2026-06-30"}],
               "drops": {"train": {"exit_after_cutoff": 2}}, "coverage": {"earnings_first_date": {"AAPL": "2019-01-29"}}}
    text = json.dumps(agents.naysayer_context(results))
    assert not re.search(r"\b(19|20)\d\d\b", text)
    assert not any(re.search(r"\b%s\b" % re.escape(t), text) for t in universe.ALL)


def test_naysayer_context_masks_dates_in_strings_only():
    results = {"what_tested": "x", "base": {"train": {"n": 2015, "mean": 0.2015}, "validation": {"n": 1999}},
               "baseline": {}, "stricter": None, "tail": {}, "drops": {"train": {"exit_after_cutoff": 2020}},
               "checks": [{"check": "leakage", "passed": True, "note": "no date after 2026-06-30"}]}
    ctx = agents.naysayer_context(results)
    assert ctx["base"]["train"] == {"n": 2015, "mean": 0.2015} and ctx["drops"]["train"]["exit_after_cutoff"] == 2020
    assert ctx["checks"][0]["note"] == "no date after [date]"
