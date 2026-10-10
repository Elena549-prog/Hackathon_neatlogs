"""Swarm: plan rules, the hard gate, round cap, fail-closed behavior, what agents can see, tracing."""
import json

import pytest

import src.swarm as swarm
from src.agents import mathematician, naysayer, planner
from src.features import FEATURE_NAMES
from src.llm import make_llm
from src.tracing import Tracer
from tests.helpers import FakeClient, FakeDeepSeekClient, FakeNeatlogs, PLAN_OUT, fake_llm, make_market

FACTS = {"ret_5d": "5-day return is 0.", "vol_20d": "20-day volatility is 0."}
FEATURES = {k: 0.0 for k in FEATURE_NAMES}
GOOD_BT = {"n": 300, "eligible": 1200, "hit_rate": 0.45, "hit_rate_low": 0.395, "conditions": {"ret_5d": [">=", 0.0]}}


def built(raw=PLAN_OUT, entry=200.0, features=FEATURES):
    return planner.build(raw, "AAA", entry, FACTS, features)


def market(label=1):
    return make_market({"AAA": [100.0] * 60}, [("AAA", 30, "validation", label)])


@pytest.fixture
def good_backtest(monkeypatch):
    monkeypatch.setattr(swarm, "backtest", lambda *a, **k: dict(GOOD_BT))


# ------------------------------------------------------------------------------ plan rules

def test_build_sets_the_fixed_levels():
    plan, err = built()
    assert err is None
    assert (plan["entry"], plan["stop"], plan["target"], plan["horizon_days"]) == (200.0, 194.0, 210.0, 10)
    assert plan["conditions"] == {"ret_5d": [">=", 0.0]}
    assert plan["direction"] == "long"


@pytest.mark.parametrize("changes, reason", [
    ({"direction": "short"}, "long"),
    ({"stop": 195.0}, "-3% and +5%"),
    ({"target": 209.0}, "-3% and +5%"),
    ({"horizon_days": 5}, "horizon_days"),
    ({"entry": 201.0}, "entry"),
    ({"facts_cited": ["close_to_ma50"]}, "not in the Researcher's facts"),
    ({"facts_cited": []}, "empty"),
    ({"conditions": {"ret_5d": [">", 0.01]}}, "does not satisfy its own condition"),
    ({"conditions": {"made_up": [">", 0.0]}}, "unknown feature"),
    ({"conditions": {"ret_5d": ["==", 0.0]}}, "unknown feature or operator"),
])
def test_validate_plan_rejects(changes, reason):
    plan, _ = built()
    plan.update(changes)
    assert reason in planner.validate_plan(plan, FACTS, FEATURES, 200.0)


def cond(features):
    return [{"feature": f, "op": ">=", "value": 0.0} for f in features]


@pytest.mark.parametrize("k, ok", [(0, False), (1, True), (4, True), (5, False)])
def test_one_to_four_conditions(k, ok):
    plan, err = built(dict(PLAN_OUT, conditions=cond(FEATURE_NAMES[:k])))
    assert (err is None) == ok
    if not ok:
        assert "need 1 to 4 conditions" in err


def test_levels_within_tolerance_pass():
    plan, _ = built()
    plan["stop"] += 0.005
    assert planner.validate_plan(plan, FACTS, FEATURES, 200.0) is None


@pytest.mark.parametrize("conditions, reason", [
    ([{"feature": "ret_5d", "op": ">=", "value": 0.0}, {"feature": "ret_5d", "op": "<", "value": 1.0}], "one condition per feature"),
    ([{"feature": "ret_5d", "op": "~", "value": 0.0}], "known feature"),
    ([{"feature": "ret_5d", "op": ">=", "value": "0"}], "known feature"),
    (["ret_5d > 0"], "known feature"),
])
def test_build_rejects_malformed_conditions(conditions, reason):
    plan, err = built(dict(PLAN_OUT, conditions=conditions))
    assert plan is None and reason in err


# ---------------------------------------------------------------------- math and the gate

def test_mathematician_uses_the_cautious_rate():
    plan = {"entry": 100.0, "stop": 97.0, "target": 105.0}
    m = mathematician.run(plan, {"n": 40, "eligible": 1000, "hit_rate": 0.6, "hit_rate_low": 0.5, "conditions": {}})
    assert m["ev_per_share"] == pytest.approx(0.5 * 5 - 0.5 * 3)       # p = lower bound, not 0.6
    assert m["size"] == 666                                           # floor(2000 / 3)
    assert m["max_loss"] == pytest.approx(1998.0)


@pytest.mark.parametrize("n, eligible, low, passes, reason", [
    (29, 1000, 0.45, False, "need at least 30"),
    (30, 1000, 0.374, False, "break-even"),
    (30, 1000, 0.376, True, None),
    (300, 1200, 0.395, True, None),
    (81, 100, 0.395, False, "too broad"),            # 81% of eligible setups
    (79, 100, 0.395, True, None),                    # 79%
    (1263, 1263, 0.378, False, "too broad"),         # spec table: all train, no real thesis
])
def test_hard_gate(n, eligible, low, passes, reason):
    plan = {"entry": 100.0, "stop": 97.0, "target": 105.0}
    math = mathematician.run(plan, {"n": n, "eligible": eligible, "hit_rate": 0.45, "hit_rate_low": low, "conditions": {}})
    llm = fake_llm()
    verdict, objections = naysayer.run(llm, {}, FACTS, math)
    assert math["gate_passed"] == passes
    assert (verdict == "approve") == passes
    assert (len(llm.calls) == 1) == passes          # a gated plan never reaches the LLM
    if reason:
        assert reason in objections[0]


def test_naysayer_approve_with_objections_becomes_a_block():
    llm = fake_llm(naysayer={"verdict": "approve", "objections": ["weak edge"]})
    math = mathematician.run({"entry": 100.0, "stop": 97.0, "target": 105.0}, GOOD_BT)
    verdict, objections = naysayer.run(llm, {}, FACTS, math)
    assert verdict == "block" and "invalid naysayer output" in objections[0]


@pytest.mark.parametrize("out, ok", [
    ({"verdict": "approve", "objections": []}, True),
    ({"verdict": "block", "objections": ["thin edge"]}, True),
    ({"verdict": "approve", "objections": ["but..."]}, False),
    ({"verdict": "block", "objections": []}, False),
    ({"verdict": "maybe", "objections": []}, False),
])
def test_validate_verdict(out, ok):
    assert (naysayer.validate_verdict(out) is None) == ok


# ------------------------------------------------------------------------- the debate loop

def test_round_cap_drops_after_two_blocks(good_backtest):
    llm = fake_llm(naysayer={"verdict": "block", "objections": ["thesis unsupported"]})
    m = market()
    rec = swarm.decide(m.setups.iloc[0].to_dict(), m, llm, Tracer())
    assert (rec["verdict"], rec["rounds"]) == ("dropped", 2)
    planner_calls = [c for c in llm.calls if c["agent"] == "planner"]
    assert len(planner_calls) == 2
    assert "thesis unsupported" in planner_calls[1]["prompt"]      # objections go back to the Planner


def test_invalid_plan_is_sent_back_with_the_reason(good_backtest):
    bad = dict(PLAN_OUT, conditions=[{"feature": "ret_5d", "op": ">", "value": 0.5}])   # today's ret_5d is 0
    llm = fake_llm(planner=lambda n: bad if n == 1 else PLAN_OUT)
    m = market()
    rec = swarm.decide(m.setups.iloc[0].to_dict(), m, llm, Tracer())
    assert (rec["verdict"], rec["rounds"]) == ("approve", 2)
    assert "does not satisfy its own condition" in [c for c in llm.calls if c["agent"] == "planner"][1]["prompt"]


def test_agents_never_see_ticker_date_label_or_price_level(good_backtest):
    m = make_market({"SECRETCO": [123.45] * 60}, [("SECRETCO", 30, "validation", 1)])
    setup = m.setups.iloc[0].to_dict()
    llm = fake_llm()
    swarm.decide(setup, m, llm, Tracer())
    for call in llm.calls:
        for leak in ("SECRETCO", setup["date"], "label", "123.45"):
            assert leak not in call["prompt"], (call["agent"], leak)


def test_run_writes_one_line_per_setup_and_simulates_after_deciding(tmp_path, good_backtest):
    m = make_market({"AAA": [100.0] * 60}, [("AAA", 30, "validation", 1), ("AAA", 31, "validation", 0)])
    out = tmp_path / "swarm.jsonl"
    swarm.run("validation", m, fake_llm(), Tracer(), out_path=str(out))
    lines = [json.loads(l) for l in out.read_text().splitlines()]
    assert len(lines) == 2
    assert all(l["verdict"] == "approve" and l["trade_outcome"] == "expired" for l in lines)
    assert [l["label"] for l in lines] == [1, 0]
    assert lines[0]["plan"]["conditions"] == {"ret_5d": [">=", 0.0]}


def test_one_failing_setup_is_logged_as_an_error_and_the_run_continues(tmp_path, good_backtest):
    m = make_market({"AAA": [100.0] * 60}, [("AAA", 30, "validation", 1), ("AAA", 31, "validation", 0)])
    llm = fake_llm(researcher=lambda n: {"facts": []} if n == 1 else {"facts": [{"key": "ret_5d", "statement": "x"}]})
    recs = swarm.run("validation", m, llm, Tracer(), out_path=str(tmp_path / "s.jsonl"))
    assert [r["verdict"] for r in recs] == ["error", "approve"]
    assert recs[0]["trade_outcome"] is None


def test_parallel_run_keeps_setup_order(tmp_path, good_backtest):
    m = make_market({"AAA": [100.0] * 80}, [("AAA", i, "validation", i % 2) for i in range(30, 50)])
    recs = swarm.run("validation", m, fake_llm(), Tracer(), out_path=str(tmp_path / "p.jsonl"), workers=8)
    assert [r["date"] for r in recs] == list(m.setups["date"])
    assert [json.loads(l)["date"] for l in (tmp_path / "p.jsonl").read_text().splitlines()] == list(m.setups["date"])


def test_refuses_the_test_split():
    with pytest.raises(SystemExit):
        swarm.run("test", market(), fake_llm(), Tracer())


# -------------------------------------------------------------------------------- tracing

def test_spans_carry_kinds_tags_and_nest_under_one_workflow_span(good_backtest):
    nl = FakeNeatlogs()
    tracer = Tracer(nl.trace)
    m = market()
    swarm.decide(m.setups.iloc[0].to_dict(), m, make_llm(tracer, client=FakeDeepSeekClient()), tracer)

    by_name = {s.name: s for s in nl.ended}
    assert {"researcher", "planner", "naysayer", "get_prices", "backtest", "mathematician", "swarm"} <= set(by_name)
    root = by_name["swarm"]
    assert root.kind == "WORKFLOW" and root.parent is None
    assert by_name["planner"].kind == "AGENT" and by_name["backtest"].kind == "TOOL"
    for s in nl.ended:
        if s is root:
            continue
        assert s.parent is root
        for key in ("agent", "round", "ticker", "date"):
            assert any(t.startswith(key + ":") for t in s.attributes["tag.tags"]), (s.name, key)
    planner_span = by_name["planner"]
    assert json.loads(planner_span.attributes["metadata"])["model"] == "deepseek-v4-pro"
    assert "output.value" in planner_span.attributes
    llm_spans = [s for s in tracer.spans if s["kind"] == "llm"]
    assert all(s["prompt_tokens"] == 1000 and s["cost"] > 0 for s in llm_spans)


def test_a_failing_step_marks_its_span_as_an_error():
    nl = FakeNeatlogs()
    tracer = Tracer(nl.trace)
    with pytest.raises(ValueError):
        with tracer.span("tool", "broken", agent="x"):
            raise ValueError("boom")
    span = nl.ended[0]
    assert span.exceptions and span.status.status_code.name == "ERROR"
    assert tracer.spans[0]["status"] == "FAILURE"


@pytest.mark.parametrize("provider, client", [("deepseek", FakeDeepSeekClient), ("claude", FakeClient)])
def test_whole_decision_works_on_each_provider(provider, client, good_backtest):
    m = market()
    rec = swarm.decide(m.setups.iloc[0].to_dict(), m, make_llm(Tracer(), provider, client()), Tracer())
    assert (rec["verdict"], rec["rounds"]) == ("approve", 1)
