"""Replay helpers: complete-line reader, capped delays, audit lookup."""
import json

from src.auditor.replay import read_events, replay_delays, find_audit_dir, clamp_speed


def ev(seq, ts):
    return {"seq": seq, "ts": ts, "audit_id": "a", "type": "x", "agent": None, "payload": {}}


def test_read_events_skips_partial_last_line(tmp_path):
    p = tmp_path / "events.jsonl"
    p.write_text(json.dumps(ev(1, "t")) + "\n\n" + json.dumps(ev(2, "t")) + "\n" + '{"seq": 3, "tru')
    assert [e["seq"] for e in read_events(p)] == [1, 2]


def test_delays_capped_and_scaled():
    events = [ev(1, "2026-10-11T12:00:00Z"), ev(2, "2026-10-11T12:00:00.500Z"), ev(3, "2026-10-11T12:00:10Z")]
    assert replay_delays(events, 1) == [0.0, 0.5, 2.0]
    assert replay_delays(events, 4) == [0.0, 0.125, 0.5]


def test_clamp_speed():
    assert clamp_speed("3") == 3.0
    assert clamp_speed("0") == 1.0 and clamp_speed("99") == 8.0
    assert clamp_speed("abc") == 1.0 and clamp_speed(None) == 1.0


def test_find_audit_dir(tmp_path):
    runs, results = tmp_path / "runs", tmp_path / "results"
    (results / "demo").mkdir(parents=True)
    (results / "demo" / "events.jsonl").write_text("")
    assert find_audit_dir("demo", [runs, results]) == results / "demo"
    assert find_audit_dir("nope", [runs, results]) is None
    assert find_audit_dir("../demo", [runs, results]) is None
