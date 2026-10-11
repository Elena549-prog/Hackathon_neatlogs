"""Event contract (AUDITOR_SPEC section 16) and the synthetic dev fixture."""
import json

from src.auditor.events import EVENT_TYPES, AGENTS, validate_event


def good(**over):
    e = {"seq": 1, "ts": "2026-10-11T12:00:00Z", "audit_id": "a1", "type": "agent_started",
         "agent": "planner", "payload": {"step": "plan"}}
    e.update(over)
    return e


def test_table_matches_spec():
    assert set(EVENT_TYPES) == {"audit_started", "agent_started", "agent_finished", "llm_call",
                                "tool_called", "tool_result", "data_progress", "backtest_result",
                                "check_result", "followup_requested", "recovered", "verdict",
                                "report_ready", "error"}
    assert EVENT_TYPES["verdict"] == ("verdict", "reason", "headline", "downgrades")
    assert AGENTS == frozenset({"planner", "researcher", "mathematician", "naysayer", "reporter", "triage"})


def test_valid_event_has_no_problems():
    assert validate_event(good()) == []


def test_problems_are_reported():
    assert validate_event(good(agent="chef"))
    assert validate_event(good(type="nope"))
    assert validate_event(good(payload={}))        # missing "step"
    assert validate_event(good(seq="1"))
    assert validate_event({"type": "verdict"})       # missing keys
    assert validate_event("not a dict")


def test_synthetic_fixture_validates(tmp_path):
    from scripts.synthetic_audit import write_synthetic_audit
    path = write_synthetic_audit(tmp_path)
    events = [json.loads(line) for line in path.read_text().splitlines()]
    assert [e["seq"] for e in events] == list(range(1, len(events) + 1))
    assert all(validate_event(e) == [] for e in events)
    assert events[0]["type"] == "audit_started"
    assert events[0]["payload"]["idea"].startswith("SYNTHETIC FIXTURE")
    assert {e["type"] for e in events} >= {"backtest_result", "followup_requested", "recovered",
                                           "verdict", "report_ready", "llm_call"}
    assert (tmp_path / "synthetic-demo" / "report.md").exists()
    # M2 follow-ups: each F* result comes after its request and carries title, result, downgrade, cause.
    requested = [(e["seq"], e["payload"]["followup"]) for e in events if e["type"] == "followup_requested"]
    results = [e for e in events if e["type"] == "backtest_result" and e["payload"]["run"].startswith("F")]
    assert 2 <= len(requested) <= 3 and [f for _, f in requested] == [e["payload"]["run"] for e in results]
    assert all(seq < r["seq"] for (seq, _), r in zip(requested, results))
    assert all({"title", "result", "downgrade", "cause"} <= set(r["payload"]) for r in results)
    met = [r["payload"]["cause"] for r in results if r["payload"]["downgrade"]]
    assert met and all(met)
    verdict = next(e for e in events if e["type"] == "verdict")["payload"]
    assert {d["cause"] for d in verdict["downgrades"]} <= set(met)
