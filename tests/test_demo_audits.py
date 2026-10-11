"""The before/after table built from copied demo audits (scripts/demo_audits.py)."""
import importlib.util
import json
from pathlib import Path

spec = importlib.util.spec_from_file_location("demo_audits", Path(__file__).resolve().parents[1] / "scripts" / "demo_audits.py")
demo = importlib.util.module_from_spec(spec)
spec.loader.exec_module(demo)


def fake_audit(root, audit_id, verdict, downgrades, runs):
    d = root / audit_id
    d.mkdir(parents=True)
    state = {"llm_calls": 4, "cost": {"usd": 0.0123},
             "steps": {"verdict": {"result": {"verdict": verdict, "downgrades": downgrades}},
                       "followups": {"result": {"runs": runs}}}}
    (d / "state.json").write_text(json.dumps(state))
    ev = [{"ts": "2026-10-12T10:00:00.000Z"}, {"ts": "2026-10-12T10:01:30.500Z"}]
    (d / "events.jsonl").write_text("\n".join(json.dumps(e) for e in ev) + "\n")


def test_table_rows_and_missing_runs(tmp_path, monkeypatch):
    monkeypatch.setattr(demo, "RESULTS", tmp_path)
    fake_audit(tmp_path, "before-straddle-sell", "promising", [], [])
    fake_audit(tmp_path, "after-straddle-sell", "inconclusive",
               [{"cause": "F4 concentration: x", "from": "promising", "to": "inconclusive"}],
               [{"id": "F4", "downgrade": True}, {"id": "F2", "downgrade": False}])
    demo.table()
    text = (tmp_path / "before_after.md").read_text()
    assert "| before | promising | none | none | 4 | $0.0123 | 90 s |" in text
    assert "| after | inconclusive | F4 concentration: x | F4 (met), F2 (not met) | 4 |" in text
    assert text.count("not run yet") == 4


def test_existing_result_is_never_overwritten(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(demo, "RESULTS", tmp_path)
    (tmp_path / "after-dips").mkdir()
    monkeypatch.setattr(demo.subprocess, "run", lambda *a, **k: (_ for _ in ()).throw(AssertionError("ran")))
    demo.run("after-dips", "buy dips in an uptrend")
    assert "skip after-dips" in capsys.readouterr().out
