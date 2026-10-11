"""Mission-control server (AUDITOR_SPEC section 16): replay SSE, report, list, static UI."""
import pytest
from fastapi.testclient import TestClient

from scripts.synthetic_audit import write_synthetic_audit
from src.auditor.server import create_app


@pytest.fixture
def slept():
    return []


@pytest.fixture
def client(tmp_path, slept):
    """Replays are paced through an injected sleep that only records the delays, so tests run fast."""
    write_synthetic_audit(tmp_path / "runs")
    (tmp_path / "ui").mkdir()
    (tmp_path / "ui" / "index.html").write_text("<h1>ui</h1>")

    async def fake_sleep(seconds):
        slept.append(seconds)

    return TestClient(create_app(roots=[tmp_path / "runs", tmp_path / "results"], ui_dist=tmp_path / "ui",
                                 sleep=fake_sleep))


def sse_events(text):
    return [b for b in text.strip().split("\n\n") if b.startswith("id:")]


def test_replay_streams_every_line_in_order(client, tmp_path):
    lines = (tmp_path / "runs/synthetic-demo/events.jsonl").read_text().splitlines()
    r = client.get("/api/audits/synthetic-demo/events?replay=1&speed=8")
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/event-stream")
    blocks = sse_events(r.text)
    assert [b.split("\n")[1][len("data: "):] for b in blocks] == lines
    assert r.text.rstrip().endswith("event: end\ndata: {}")


def test_replay_is_paced_by_capped_timestamp_gaps(client, slept, tmp_path):
    from src.auditor.replay import read_events, replay_delays
    events = read_events(tmp_path / "runs/synthetic-demo/events.jsonl")
    client.get("/api/audits/synthetic-demo/events?replay=1&speed=4")
    assert slept == [d for d in replay_delays(events, 4) if d]
    assert max(slept) == 2.0 / 4


def test_replay_from_seq_skips_shown_events(client):
    r = client.get("/api/audits/synthetic-demo/events?replay=1&speed=8&from=5")
    assert sse_events(r.text)[0].startswith("id: 6\n")
    r = client.get("/api/audits/synthetic-demo/events?replay=1&speed=8", headers={"Last-Event-ID": "5"})
    assert sse_events(r.text)[0].startswith("id: 6\n")


def test_bad_speed_clamps(client):
    assert client.get("/api/audits/synthetic-demo/events?replay=1&speed=banana").status_code == 200


def test_unknown_audit_404(client):
    assert client.get("/api/audits/nope/events?replay=1").status_code == 404
    assert client.get("/api/audits/nope/report").status_code == 404


def test_report_and_list(client):
    assert "Synthetic fixture" in client.get("/api/audits/synthetic-demo/report").text
    [a] = client.get("/api/audits").json()
    assert a["audit_id"] == "synthetic-demo" and a["finished"] is True and a["idea"].startswith("SYNTHETIC")


def test_ui_served(client):
    assert "<h1>ui</h1>" in client.get("/").text


# --- live mode (Task 4): a fake child that writes audit_started and exits without a verdict ---
import json
import sys
import time

from src.auditor.server import AuditRunner

FAKE_CHILD = """
import json, sys, time, pathlib
root, aid = pathlib.Path(sys.argv[1]), sys.argv[2]
d = root / aid; d.mkdir(parents=True, exist_ok=True)
(d / "events.jsonl").write_text(json.dumps({"seq": 1, "ts": "2026-10-11T12:00:00Z", "audit_id": aid,
    "type": "audit_started", "agent": None,
    "payload": {"idea": sys.argv[3], "trace_id": "t", "llm_budget": 8, "fault": None}}) + "\\n")
time.sleep(0.3)
"""


@pytest.fixture
def live(tmp_path):
    root = tmp_path / "runs"
    runner = AuditRunner(root, command=lambda aid, idea: [sys.executable, "-c", FAKE_CHILD, str(root), aid, idea])
    return TestClient(create_app(roots=[root], ui_dist=tmp_path / "none", runner=runner)), root, runner


def wait_for(predicate, timeout=3.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(0.05)
    return False


def test_post_starts_and_409_while_running(live):
    client, root, runner = live
    r = client.post("/api/audits", json={"idea": "SYNTHETIC FIXTURE: test"})
    assert r.status_code == 200 and r.json()["audit_id"]
    assert runner.running
    assert client.post("/api/audits", json={"idea": "another"}).status_code == 409
    assert wait_for(lambda: not runner.running)


def test_child_without_verdict_gets_error_event(live):
    client, root, runner = live
    aid = client.post("/api/audits", json={"idea": "x"}).json()["audit_id"]
    path = root / aid / "events.jsonl"

    def last_is_error():
        lines = path.read_text().splitlines() if path.exists() else []
        return bool(lines) and json.loads(lines[-1])["type"] == "error"

    assert wait_for(last_is_error)
    events = [json.loads(l) for l in path.read_text().splitlines()]
    assert [e["seq"] for e in events] == [1, 2]
    assert events[1]["agent"] is None and "without a verdict" in events[1]["payload"]["message"]


def test_live_stream_ends_after_error(live):
    client, root, runner = live
    aid = client.post("/api/audits", json={"idea": "x"}).json()["audit_id"]
    r = client.get("/api/audits/%s/events" % aid)
    blocks = sse_events(r.text)
    assert [json.loads(b.split("\n")[1][6:])["type"] for b in blocks] == ["audit_started", "error"]
    assert r.text.rstrip().endswith("event: end\ndata: {}")


def test_post_without_idea_is_422(live):
    client, _, _ = live
    assert client.post("/api/audits", json={}).status_code == 422
