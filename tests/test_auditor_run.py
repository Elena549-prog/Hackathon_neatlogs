"""The audit orchestrator end to end on synthetic data with the fake LLM (AUDITOR_SPEC sections 4, 8, 12)."""
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.auditor import run as runmod
from src.auditor.events import validate_event
from src.auditor.fake_llm import FakeAuditorClient, make_fake_llm
from src.auditor.plan import plan_hash
from src.llm import LLMError, make_llm
from src.tracing import Tracer

TICKERS = ["AAPL", "MSFT", "NVDA"]      # real names so the universe lookup finds them (mega_cap, tech, all_50)


def walk(seed, start="2024-01-02", end="2026-07-29", level=100.0):
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range(start, end)
    adj = level * np.cumprod(1 + rng.normal(0.0003, 0.015, len(dates)))
    close = adj * 1.01
    return pd.DataFrame({"Open": close * (1 + rng.normal(0, 0.003, len(dates))), "High": close * 1.012, "Low": close * 0.988,
                         "Close": close, "Adj Close": adj, "Volume": 1e6 * (1 + rng.random(len(dates)))}, index=dates)


class World:
    def __init__(self):
        self.frames = {t: walk(i) for i, t in enumerate(TICKERS)}
        self.frames["SPY"], self.frames["^VIX"] = walk(10, level=400), walk(11, level=20)
        dates = self.frames["AAPL"].index
        self.iv = pd.DataFrame({"date": np.tile(dates, len(TICKERS)), "ticker": np.repeat(TICKERS, len(dates)),
                                "iv_current": 0.3, "hv_current": 0.25})
        self.earnings = {t: [pd.Timestamp("2025-01-30"), pd.Timestamp("2025-04-30"), pd.Timestamp("2026-01-29"), pd.Timestamp("2026-04-29")]
                         for t in TICKERS}
        self.calls = {"prices": 0, "iv": 0, "earnings": 0}
        self.fetchers = {"prices": self.prices, "iv": self.ivf, "earnings": self.earn}

    def prices(self, tickers, cache_dir, **kw):
        self.calls["prices"] += 1
        return {t: self.frames[t] for t in list(tickers) + ["SPY", "^VIX"] if t in self.frames}, [t for t in tickers if t not in self.frames]

    def ivf(self, tickers, cache_dir, on_recovered=None, fault_first_timeout=False, **kw):
        self.calls["iv"] += 1
        if fault_first_timeout and on_recovered:
            on_recovered("DoltHub timeout on window 2026-06-01..2026-06-14 (injected)", "halved the window and retried")
        return self.iv[self.iv.ticker.isin(tickers)]

    def earn(self, tickers, cache_dir, **kw):
        self.calls["earnings"] += 1
        return {t: self.earnings.get(t, []) for t in tickers}


@pytest.fixture
def world():
    return World()


def go(world, tmp_path, idea="buy dips in an uptrend", llm=None, tracer=None, **kw):
    tracer = tracer or Tracer()
    llm = llm or make_fake_llm(tracer)
    return runmod.run_audit(idea, "a1", llm, tracer, root=tmp_path / "audits", cache_dir=tmp_path / "cache",
                            fetchers=world.fetchers, provider="fake", **kw)


def events_of(tmp_path):
    return [json.loads(l) for l in (tmp_path / "audits" / "a1" / "events.jsonl").read_text().splitlines()]


def test_end_to_end_writes_everything(world, tmp_path):
    out = go(world, tmp_path)
    assert out["verdict"]["verdict"] in ("kill", "inconclusive", "promising", "cannot_audit")
    ev = events_of(tmp_path)
    assert [e["seq"] for e in ev] == list(range(1, len(ev) + 1)) and all(validate_event(e) == [] for e in ev)
    types = [e["type"] for e in ev]
    assert types[0] == "audit_started" and "verdict" in types and types[-1] in ("report_ready", "agent_finished")
    assert types.index("verdict") < types.index("report_ready")
    assert {"backtest_result", "check_result", "llm_call", "tool_called", "tool_result", "data_progress"} <= set(types)
    state = json.loads((tmp_path / "audits" / "a1" / "state.json").read_text())
    assert state["steps"]["plan"]["result"]["hash"] == plan_hash(state["steps"]["plan"]["result"]["plan"])
    report = Path(out["report_path"]).read_text()
    assert report.splitlines()[2].startswith("stock_long on all_50") and state["steps"]["plan"]["result"]["hash"] in report
    assert "FAKE LLM" in report
    assert len((tmp_path / "audits" / "registry.jsonl").read_text().splitlines()) == 1
    assert state["llm_calls"] == 3 and out["events_path"].endswith("events.jsonl")


def test_plan_is_frozen_before_backtest(world, tmp_path):
    go(world, tmp_path)
    ev = events_of(tmp_path)
    planner_done = next(i for i, e in enumerate(ev) if e["type"] == "agent_finished" and e["agent"] == "planner")
    first_bt = next(i for i, e in enumerate(ev) if e["type"] == "backtest_result")
    assert planner_done < first_bt
    assert sum(1 for e in ev if e["type"] == "llm_call" and e["agent"] == "planner") == 1
    summary = ev[planner_done]["payload"]["summary"]
    assert summary["what_tested"].startswith("stock_long") and len(summary["plan_hash"]) == 64
    base = next(e for e in ev if e["type"] == "backtest_result")
    assert base["payload"]["run"] == "base" and len(base["payload"]["equity_train"]) <= 300
    assert set(base["payload"]["validation"]) >= {"n", "blocks", "mean", "ci_low", "ci_high"}


def test_refusal_short_circuits(world, tmp_path):
    out = go(world, tmp_path, idea="pump the stock with coordinated buying")
    assert out["verdict"] == {"verdict": "cannot_audit", "reason": "refused", "headline": {}, "downgrades": []}
    assert world.calls == {"prices": 0, "iv": 0, "earnings": 0}
    assert not any(e["type"] in ("tool_called", "backtest_result") for e in events_of(tmp_path))
    assert "Refused" in Path(out["report_path"]).read_text()


def test_core_trigger_untestable(world, tmp_path):
    out = go(world, tmp_path, idea="buy when twitter sentiment turns positive")
    assert out["verdict"]["verdict"] == "cannot_audit" and "not testable" in out["verdict"]["reason"]
    assert world.calls["prices"] == 0


def test_invalid_plan_twice(world, tmp_path):
    calls = []

    def llm(agent, system, prompt, schema, **tags):
        calls.append(agent)
        if agent == "planner":
            return {"refuse": {"is_refused": False, "reason": ""}, "family": "crypto", "universe_group": "all_50",
                    "conditions": [], "hypothesis": "", "assumptions": [], "not_tested": [], "core_trigger_tested": True}
        return {"critique": "c", "doubts": [], "prose": "p"}

    out = go(world, tmp_path, llm=llm)
    assert out["verdict"]["verdict"] == "cannot_audit" and out["verdict"]["reason"] == "no valid plan"
    assert calls.count("planner") == 2


def test_budget_cap(world, tmp_path, monkeypatch):
    monkeypatch.setattr(runmod, "NON_REPORTER_CAP", 1)
    out = go(world, tmp_path)
    state = json.loads((tmp_path / "audits" / "a1" / "state.json").read_text())
    report = Path(out["report_path"]).read_text()
    assert state["llm_calls"] == 2 and "LLM call cap" in report and out["verdict"]["verdict"] != "cannot_audit"
    assert any(e["type"] == "llm_call" and e["agent"] == "reporter" for e in events_of(tmp_path))


def test_reporter_error_ships_template(world, tmp_path):
    tracer = Tracer()
    inner = make_fake_llm(tracer)

    def llm(agent, *a, **kw):
        if agent == "reporter":
            raise LLMError("reporter: empty reply after 2 attempts")
        return inner(agent, *a, **kw)

    out = go(world, tmp_path, llm=llm, tracer=tracer)
    ready = next(e for e in events_of(tmp_path) if e["type"] == "report_ready")
    assert ready["payload"]["prose_included"] is False and "Reporter prose: not included" in Path(out["report_path"]).read_text()


def test_prose_banned_phrase_dropped(world, tmp_path):
    tracer = Tracer()
    inner = make_fake_llm(tracer)

    def llm(agent, *a, **kw):
        return {"prose": "You should buy this, it is guaranteed."} if agent == "reporter" else inner(agent, *a, **kw)

    out = go(world, tmp_path, llm=llm, tracer=tracer)
    assert "guaranteed" not in Path(out["report_path"]).read_text()
    assert next(e for e in events_of(tmp_path) if e["type"] == "report_ready")["payload"]["prose_included"] is False


def test_fault_llm_empty_recovers(world, tmp_path):
    tracer = Tracer()
    client = FakeAuditorClient(queued={"planner": [""]})
    llm = make_llm(tracer, "deepseek", client)
    out = go(world, tmp_path, llm=llm, tracer=tracer, fault="llm_empty")
    rec = [e for e in events_of(tmp_path) if e["type"] == "recovered"]
    assert rec and rec[0]["payload"]["injected"] is True and "empty" in rec[0]["payload"]["failed"]
    assert "INJECTED" in Path(out["report_path"]).read_text()
    started = events_of(tmp_path)[0]["payload"]
    assert started["fault"] == "llm_empty" and started["llm_budget"] == 8 and started["provider"] == "fake"


def test_fault_dolthub_timeout_recovers(world, tmp_path):
    out = go(world, tmp_path, idea="sell straddles on low-volatility mega-caps", fault="dolthub_timeout")
    rec = [e for e in events_of(tmp_path) if e["type"] == "recovered"]
    assert rec and rec[0]["payload"]["injected"] is True and "DoltHub" in rec[0]["payload"]["failed"]
    assert world.calls["iv"] == 1
    base = next(e for e in events_of(tmp_path) if e["type"] == "backtest_result" and e["payload"]["run"] == "base")
    assert "stricter_cost" in [e["payload"]["run"] for e in events_of(tmp_path) if e["type"] == "backtest_result"]
    assert out["verdict"]["verdict"] in ("kill", "inconclusive", "promising") and base["payload"]["train"]["n"] >= 0


def test_resume_after_backtest(world, tmp_path):
    tracer = Tracer()
    inner = make_fake_llm(tracer)
    planner_calls = []

    def flaky(agent, *a, **kw):
        if agent == "planner":
            planner_calls.append(1)
        if agent == "naysayer":
            raise RuntimeError("network down")
        return inner(agent, *a, **kw)

    with pytest.raises(RuntimeError):
        go(world, tmp_path, llm=flaky, tracer=tracer)
    first = events_of(tmp_path)
    assert first[-1]["type"] == "error" and not any(e["type"] == "verdict" for e in first)

    def fixed(agent, *a, **kw):
        if agent == "planner":
            planner_calls.append(1)
        return inner(agent, *a, **kw)

    out = go(world, tmp_path, llm=fixed, tracer=tracer, resume=True)
    ev = events_of(tmp_path)
    assert out["verdict"]["verdict"] != "cannot_audit" and len(planner_calls) == 1
    assert [e["seq"] for e in ev] == list(range(1, len(ev) + 1)) and len(ev) > len(first)
    assert sum(1 for e in ev if e["type"] == "backtest_result" and e["payload"]["run"] == "base") == 1
    state = json.loads((tmp_path / "audits" / "a1" / "state.json").read_text())
    assert state["steps"]["plan"]["status"] == "done" and state["steps"]["verdict"]["status"] == "done"


def test_leakage_error_is_audit_error(world, tmp_path, monkeypatch):
    from src.auditor import backtest
    monkeypatch.setattr(backtest, "VALID", ("2026-01-01", "2026-07-31"))
    with pytest.raises(runmod.AuditError):
        go(world, tmp_path, idea="buy every day")
    ev = events_of(tmp_path)
    assert ev[-1]["type"] == "error" and "leak" in ev[-1]["payload"]["message"].lower()
    assert not any(e["type"] == "verdict" for e in ev)


def test_nan_never_reaches_events_or_report(world, tmp_path):
    def llm(agent, system, prompt, schema, **tags):
        if agent == "planner":
            return {"refuse": {"is_refused": False, "reason": ""}, "family": "stock_long", "universe_group": "mega_cap",
                    "conditions": [{"feature": "ret_5d", "op": "<", "value": -0.9}],
                    "exit": {"target_pct": 0.05, "stop_pct": 0.03, "horizon_days": 10}, "hypothesis": "h",
                    "assumptions": [], "not_tested": [], "core_trigger_tested": True}
        return {"critique": "c", "doubts": [], "prose": "p"}

    out = go(world, tmp_path, llm=llm)
    text = (tmp_path / "audits" / "a1" / "events.jsonl").read_text()
    assert "NaN" not in text and "Infinity" not in text
    assert out["verdict"]["verdict"] == "inconclusive" and out["verdict"]["headline"]["paired_ci_low"] is None
    assert "n/a" in Path(out["report_path"]).read_text()


def test_existing_id_without_resume_is_refused(world, tmp_path):
    go(world, tmp_path)
    before = (tmp_path / "audits" / "a1" / "events.jsonl").read_text()
    with pytest.raises(runmod.AuditError):
        go(world, tmp_path)
    assert (tmp_path / "audits" / "a1" / "events.jsonl").read_text() == before
    assert len((tmp_path / "audits" / "registry.jsonl").read_text().splitlines()) == 1


def test_spans_and_trace_id(world, tmp_path):
    from tests.helpers import FakeNeatlogs

    class WithContext(FakeNeatlogs):
        def trace(self, name, kind=None, **attributes):
            import contextlib

            @contextlib.contextmanager
            def cm():
                with super(WithContext, self).trace(name, kind=kind, **attributes) as span:
                    span.get_span_context = lambda: type("C", (), {"trace_id": 0xABC})()
                    yield span
            return cm()

    fake = WithContext()
    tracer = Tracer(open_span=fake.trace)
    go(world, tmp_path, tracer=tracer)
    kinds = {s["kind"] for s in tracer.spans}
    assert {"workflow", "agent", "tool", "llm"} <= kinds
    assert tracer.trace_id == format(0xABC, "032x")
    ev = events_of(tmp_path)
    assert ev[0]["payload"]["trace_id"] == tracer.trace_id
    assert next(e for e in ev if e["type"] == "report_ready")["payload"]["trace_id"] == tracer.trace_id
    workflow = next(s for s in tracer.spans if s["kind"] == "workflow")
    assert workflow["tags"]["audit_id"] == "a1"
