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
