"""EventLog (events.jsonl writer) and the Tracer's on_span callback."""
import json

import pytest

from src.auditor.eventlog import EventLog
from src.auditor.events import validate_event
from src.tracing import Tracer


def test_emit_numbers_and_validates(tmp_path):
    log = EventLog(tmp_path / "events.jsonl", "a1")
    e1 = log.emit("audit_started", None, {"idea": "x", "trace_id": None, "llm_budget": 8, "fault": None})
    e2 = log.emit("agent_started", "planner", {"step": "plan"})
    assert (e1["seq"], e2["seq"]) == (1, 2) and log.seq == 2
    lines = [json.loads(l) for l in (tmp_path / "events.jsonl").read_text().splitlines()]
    assert [validate_event(e) for e in lines] == [[], []]
    assert lines[1]["ts"].endswith("Z") and lines[1]["audit_id"] == "a1"


def test_emit_rejects_bad_payload(tmp_path):
    log = EventLog(tmp_path / "events.jsonl", "a1")
    with pytest.raises(ValueError):
        log.emit("verdict", None, {})
    assert not (tmp_path / "events.jsonl").exists() or (tmp_path / "events.jsonl").read_text() == ""


def test_resume_continues_seq(tmp_path):
    p = tmp_path / "events.jsonl"
    lines = [json.dumps({"seq": i, "ts": "t", "audit_id": "a1", "type": "agent_started", "agent": "planner",
                         "payload": {"step": "s"}}) for i in (1, 2, 3)]
    p.write_text("\n".join(lines) + "\n" + '{"seq": 4, "tru')
    log = EventLog.resume(p, "a1")
    assert log.emit("agent_started", "planner", {"step": "s"})["seq"] == 4


def test_tracer_on_span_callback():
    recs = []
    tracer = Tracer(on_span=recs.append)
    with tracer.span("llm", "planner", model="m", step="plan") as rec:
        rec["attempts"] = 2
    assert len(recs) == 1 and recs[0]["kind"] == "llm" and recs[0]["attempts"] == 2
    assert recs[0]["status"] == "SUCCESS" and recs[0]["tags"] == {"step": "plan"}
