"""The audit loop end to end on synthetic data with fake LLMs (spec sections 4, 8, 9, 12, 16)."""
import json
import os

import pandas as pd
import pytest

from src.auditor import audit as audit_mod
from src.auditor.__main__ import EmptyOnce
from src.auditor.audit import Audit, BudgetExceeded
from src.auditor.data import fetch_iv_window
from src.llm import make_llm
from src.tracing import Tracer
from tests.auditor_helpers import FakeFetchers, FakeOpenAI, fake_llm, plan_reply

STRADDLE = plan_reply("straddle_buy", "energy", [{"feature": "iv_hv_ratio", "op": ">", "value": 1.0}])


@pytest.fixture
def env(tmp_path):
    """(runs_dir, cache_dir, fetchers) shared by the tests in one function."""
    return str(tmp_path / "runs"), str(tmp_path / "cache"), FakeFetchers()


def run_audit(env, llm=None, idea="buy dips", audit_id="a1", fault=None, **kw):
    runs, cache, fetch = env
    a = Audit(audit_id, llm or fake_llm(), Tracer(), runs_dir=runs, fetch=fetch, cache_dir=cache,
              sleep=lambda s: None, **kw)
    return a, a.start(idea, fault=fault)


def events(a):
    with open(os.path.join(a.dir, "events.jsonl"), encoding="utf-8") as f:
        return [json.loads(l) for l in f]


# --------------------------------------------------------------------------------- the loop

def test_end_to_end_writes_report_state_events_and_registry(env):
    a, st = run_audit(env)
    assert st["verdict"]["verdict"] in ("kill", "inconclusive", "promising")
    for name in ("report.md", "state.json", "events.jsonl"):
        assert os.path.exists(os.path.join(a.dir, name))
    report = open(os.path.join(a.dir, "report.md"), encoding="utf-8").read()
    assert st["plan_hash"] in report and st["what_was_tested"] in report
    assert "Not financial advice" in report and "survivorship" in report
    reg = [json.loads(l) for l in open(a.registry, encoding="utf-8")]
    assert reg[-1]["plan_hash"] == st["plan_hash"] and reg[-1]["verdict"] == st["verdict"]["verdict"]
    types = [e["type"] for e in events(a)]
    assert types[0] == "audit_started" and types[-1] == "report_ready"
    assert "verdict" in types and "backtest_result" in types and "check_result" in types


def test_plan_is_frozen_with_its_hash_before_any_data_fetch(env):
    runs, cache, _ = env

    class Checking(FakeFetchers):
        def prices(self, tickers, start, end):
            with open(os.path.join(runs, "freeze", "state.json"), encoding="utf-8") as f:
                st = json.load(f)
            assert st["plan_v0"] and len(st["plan_hash"]) == 64
            return super().prices(tickers, start, end)

    a, st = run_audit((runs, cache, Checking()), audit_id="freeze")
    assert st["plan_hash"] == audit_mod.plan_hash(st["plan_v0"])
    assert [c["role"] for c in a.llm.calls].count("planner") == 1


def test_shared_window_count_grows_with_each_audit(env):
    a1, s1 = run_audit(env, audit_id="w1")
    a2, s2 = run_audit(env, audit_id="w2")
    assert s1["results"]["shared_window_audits"] == 1 and s2["results"]["shared_window_audits"] == 2
    assert "2 audits have used the validation window" in open(os.path.join(a2.dir, "report.md")).read()


def test_straddle_audit_runs_stricter_cost_and_cost_realism(env):
    a, st = run_audit(env, llm=fake_llm(planner=STRADDLE))
    assert "stricter" in st["results"]
    assert any(c["check"] == "cost_realism" for c in st["results"]["checks"])


def test_m1_run_without_followups_makes_two_llm_calls(env):
    a, st = run_audit(env, followups=False)
    assert [c["role"] for c in a.llm.calls] == ["planner", "reporter"]
    assert st["followups"] == [] and st["naysayer_1"] is None


def test_followups_are_run_and_logged(env):
    ask = {"doubts": ["maybe one year"], "followups": [{"id": "F2", "reason": "years"}, {"id": "F3", "reason": "h"},
                                                       {"id": "F4", "reason": "c"}, {"id": "F1", "reason": "e"}]}
    a, st = run_audit(env, llm=fake_llm(naysayer_1=ask))
    assert [f["id"] for f in st["followups"]] == ["F2", "F3", "F4"]          # capped at 3
    assert all("note" in f and "reason" in f for f in st["followups"])
    assert sum(e["type"] == "followup_requested" for e in events(a)) == 3


# --------------------------------------------------------------------------- cannot_audit

def test_refused_idea_makes_no_fetch_and_no_backtest(env):
    a, st = run_audit(env, llm=fake_llm(planner=plan_reply(refuse=True)), idea="pump and dump a small cap")
    assert st["verdict"]["verdict"] == "cannot_audit" and st["verdict"]["reason"].startswith("refused")
    assert env[2].calls == {"prices": 0, "dolthub": 0, "earnings": 0}
    assert not any(e["type"] in ("tool_called", "backtest_result") for e in events(a))


def test_core_trigger_not_tested_is_cannot_audit(env):
    a, st = run_audit(env, llm=fake_llm(planner=plan_reply(core=False)), idea="buy on bullish tweets")
    assert st["verdict"] == {"verdict": "cannot_audit", "downgrades": [],
                             "reason": "core of the idea not testable with available data"}
    assert env[2].calls["prices"] == 0


def test_invalid_twice_is_cannot_audit_and_the_planner_gets_the_reason(env):
    bad = plan_reply(group="faang")
    a, st = run_audit(env, llm=fake_llm(planner=bad))
    assert st["verdict"]["verdict"] == "cannot_audit" and "no valid plan" in st["verdict"]["reason"]
    planner_calls = [c for c in a.llm.calls if c["role"] == "planner"]
    assert len(planner_calls) == 2 and "universe_group" in planner_calls[1]["prompt"]


def test_invalid_then_valid_plan_is_used(env):
    replies = lambda n: plan_reply(group="faang") if n == 1 else plan_reply()
    a, st = run_audit(env, llm=fake_llm(planner=replies))
    assert st["verdict"]["verdict"] != "cannot_audit" and st["plan_v0"]["universe_group"] == "energy"


# ---------------------------------------------------------------------- budget and reporter

def test_budget_refuses_the_8th_non_reporter_call(env):
    # a refused idea uses 1 planner call and the Reporter's call; then call the Naysayer by hand
    a, st = run_audit(env, llm=fake_llm(planner=plan_reply(refuse=True)), audit_id="b2")
    schema = {"type": "object", "properties": {}, "required": []}
    for _ in range(7 - st["llm"]["nonreporter"]):
        a.call("naysayer", "s", "{}", schema, "naysayer_2")
    with pytest.raises(BudgetExceeded):
        a.call("naysayer", "s", "{}", schema, "naysayer_2")
    assert a.state["llm"]["cap_hit"] and a.state["llm"]["nonreporter"] == 7 and a.state["llm"]["calls"] == 8
    with pytest.raises(BudgetExceeded):                         # the Reporter's single call is already used
        a.call("reporter", "s", "{}", schema, "report")


def test_cap_hit_ends_the_loop_with_the_evidence_and_the_reporter_still_runs(env, monkeypatch):
    monkeypatch.setattr(audit_mod, "NONREPORTER_CAP", 2)        # planner + naysayer call 1
    a, st = run_audit(env, audit_id="cap")
    assert st["llm"]["cap_hit"] and st["naysayer_2"] is None
    assert st["llm"]["reporter"] == 1 and st["reporter_prose"]
    assert "cap was hit" in open(os.path.join(a.dir, "report.md")).read()


def test_reporter_error_ships_the_template_without_prose(env):
    a, st = run_audit(env, llm=fake_llm(reporter=RuntimeError("boom")))
    assert st["reporter_prose"] is None
    assert events(a)[-1]["payload"]["prose_included"] is False
    assert "## Explanation" not in open(os.path.join(a.dir, "report.md")).read()


def test_prose_with_a_banned_phrase_is_dropped(env):
    a, st = run_audit(env, llm=fake_llm(reporter={"prose": "This is a sure thing and we recommend it."}))
    assert st["reporter_prose"] is None and any("banned" in n for n in st["notes"])


# ----------------------------------------------------------------------------------- faults

def test_fault_llm_empty_recovers_and_is_labeled_injected(env):
    replies = [plan_reply(), {"doubts": [], "followups": []}, {"critique": "ok"}, {"prose": "fine"}]
    fired = []
    llm = make_llm(Tracer(), "deepseek", EmptyOnce(FakeOpenAI(replies), fired))
    llm.fault_fired = fired
    runs, cache, fetch = env
    a = Audit("f1", llm, _tracer_of(llm), runs_dir=runs, fetch=fetch, cache_dir=cache)
    st = a.start("buy dips", fault="llm_empty")
    rec = [e for e in events(a) if e["type"] == "recovered"]
    assert len(rec) == 1 and rec[0]["payload"]["injected"] is True
    assert "[INJECTED]" in open(os.path.join(a.dir, "report.md")).read()
    assert st["llm"]["calls"] == 4 and st["llm"]["prompt_tokens"] > 0       # retry is not an extra call


def _tracer_of(llm):
    """The Tracer captured by make_llm's closure, so Audit reads the same spans."""
    for cell in llm.__closure__:
        if isinstance(cell.cell_contents, Tracer):
            return cell.cell_contents
    raise AssertionError("no tracer in closure")


def test_fault_dolthub_timeout_recovers_and_is_labeled_injected(env):
    a, st = run_audit(env, llm=fake_llm(planner=STRADDLE), fault="dolthub_timeout")
    rec = [e["payload"] for e in events(a) if e["type"] == "recovered"]
    assert rec and rec[0]["injected"] is True and "DoltHub" in rec[0]["failed"]
    assert "[INJECTED]" in open(os.path.join(a.dir, "report.md")).read()


def test_dolthub_timeouts_on_14_day_windows_halve_and_succeed():
    fetch = FakeFetchers(timeout_if_longer_than=7)
    seen = []
    rows = fetch_iv_window(fetch, ["XOM"], pd.Timestamp("2024-01-01"), pd.Timestamp("2024-01-14"),
                           sleep=lambda s: None, on_recovered=lambda *a: seen.append(a))
    assert {r["date"] for r in rows} >= {"2024-01-02", "2024-01-12"}
    assert ("2024-01-01", "2024-01-07") in fetch.windows and seen and "halved" in seen[0][1]
    assert seen[0][2] is False                                           # a real failure: labeled REAL


# ----------------------------------------------------------------------------------- resume

def test_resume_after_the_backtest_skips_planner_and_fetch_and_continues_seq(env, monkeypatch):
    runs, cache, fetch = env

    def crash(self):
        raise KeyboardInterrupt("simulated crash")

    monkeypatch.setattr(Audit, "_step_naysayer_1", crash)
    a = Audit("r1", fake_llm(), Tracer(), runs_dir=runs, fetch=fetch, cache_dir=cache)
    with pytest.raises(KeyboardInterrupt):
        a.start("buy dips")
    assert "backtest" in a.state["done"]
    last_seq = events(a)[-1]["seq"]
    monkeypatch.undo()

    fetch2, llm2 = FakeFetchers(), fake_llm()
    b = Audit("r1", llm2, Tracer(), runs_dir=runs, fetch=fetch2, cache_dir=cache)
    st = b.resume()
    assert fetch2.calls == {"prices": 0, "dolthub": 0, "earnings": 0}
    assert "planner" not in [c["role"] for c in llm2.calls]
    seqs = [e["seq"] for e in events(b)]
    assert seqs == list(range(len(seqs))) and seqs[-1] > last_seq
    assert st["verdict"] and st["plan_hash"] == a.state["plan_hash"]


# ----------------------------------------------------------------------------- event contract

PAYLOAD = {
    "audit_started": {"idea", "trace_id", "llm_budget", "fault"},
    "agent_started": {"step"},
    "agent_finished": {"step", "status", "duration_ms", "summary"},
    "llm_call": {"model", "prompt_tokens", "completion_tokens", "cost_usd", "latency_ms"},
    "tool_called": {"tool", "args"},
    "tool_result": {"tool", "ok", "duration_ms", "summary"},
    "data_progress": {"what", "percent"},
    "backtest_result": {"run", "train", "validation", "baseline", "equity_train", "equity_validation", "histogram"},
    "check_result": {"check", "passed", "value", "note"},
    "followup_requested": {"followup", "reason"},
    "recovered": {"failed", "action", "injected"},
    "verdict": {"verdict", "reason", "headline", "downgrades"},
    "report_ready": {"path", "trace_id", "prose_included"},
    "error": {"step", "message"},
}
AGENTS = {"planner", "researcher", "mathematician", "naysayer", "reporter", "triage", None}


@pytest.mark.parametrize("planner, fault", [(None, None), (STRADDLE, "dolthub_timeout"), (plan_reply(refuse=True), None)])
def test_every_event_matches_the_contract(env, planner, fault):
    a, _ = run_audit(env, llm=fake_llm(planner=planner) if planner else None, fault=fault)
    evs = events(a)
    assert [e["seq"] for e in evs] == list(range(len(evs)))
    for e in evs:
        assert set(e) == {"seq", "ts", "audit_id", "type", "agent", "payload"}
        assert e["audit_id"] == a.id and e["agent"] in AGENTS and e["ts"].endswith("Z")
        assert e["type"] in PAYLOAD, e["type"]
        assert PAYLOAD[e["type"]] <= set(e["payload"]), (e["type"], e["payload"].keys())
    for e in evs:
        if e["type"] == "backtest_result" and e["payload"]["run"] == "base":
            v = e["payload"]["validation"]
            assert {"n", "blocks", "win_rate", "mean", "median", "ci_low", "ci_high", "worst_trade", "worst_window"} <= set(v)
            assert len(e["payload"]["equity_train"]) <= 301
            assert len(e["payload"]["histogram"]["counts"]) == 20
