"""CLI (AUDITOR_SPEC section 9): balance check, fake provider end to end, resume flag."""
import json
from pathlib import Path

import pytest

from src.auditor import __main__ as cli
from tests.test_auditor_run import World


def test_balance_parse(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "x")
    payload = {"is_available": True, "balance_infos": [{"currency": "USD", "total_balance": "12.50", "granted_balance": "0", "topped_up_balance": "12.50"}]}
    assert cli.deepseek_balance(get=lambda url, headers: payload) == 12.5
    assert cli.deepseek_balance(get=lambda url, headers: (_ for _ in ()).throw(RuntimeError("down"))) is None


def test_refuses_low_balance(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "x")
    monkeypatch.setattr(cli, "deepseek_balance", lambda get=None: 1.5)
    rc = cli.main(["--root", str(tmp_path / "audits"), "--cache", str(tmp_path / "cache"), "buy dips in an uptrend"])
    assert rc == 2 and not (tmp_path / "audits").exists() and "balance" in capsys.readouterr().out.lower()


def test_unknown_balance_refuses_without_flag(tmp_path, monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "x")
    monkeypatch.setattr(cli, "deepseek_balance", lambda get=None: None)
    assert cli.main(["--root", str(tmp_path / "audits"), "buy dips in an uptrend"]) == 2


def test_fake_provider_runs_end_to_end(tmp_path, monkeypatch, capsys):
    world = World()
    monkeypatch.setattr(cli, "make_fetchers", lambda fault: world.fetchers)
    rc = cli.main(["--provider", "fake", "--id", "demo1", "--root", str(tmp_path / "audits"), "--cache", str(tmp_path / "cache"),
                   "buy dips in an uptrend"])
    out = capsys.readouterr().out
    assert rc == 0 and "verdict:" in out.lower() and (tmp_path / "audits" / "demo1" / "report.md").exists()
    assert (tmp_path / "audits" / "demo1" / "events.jsonl").exists()
    assert json.loads((tmp_path / "audits" / "demo1" / "state.json").read_text())["steps"]["report"]["status"] == "done"


def test_resume_flag(tmp_path, monkeypatch):
    world = World()
    monkeypatch.setattr(cli, "make_fetchers", lambda fault: world.fetchers)
    rc = cli.main(["--provider", "fake", "--id", "demo2", "--root", str(tmp_path / "audits"), "--cache", str(tmp_path / "cache"),
                   "buy dips in an uptrend"])
    assert rc == 0
    rc2 = cli.main(["--provider", "fake", "--root", str(tmp_path / "audits"), "--cache", str(tmp_path / "cache"), "--resume", "demo2"])
    assert rc2 == 0
    ev = [json.loads(l) for l in (tmp_path / "audits" / "demo2" / "events.jsonl").read_text().splitlines()]
    assert sum(1 for e in ev if e["type"] == "verdict") == 1              # everything was done; nothing re-run


def test_fault_flag_is_validated(tmp_path):
    with pytest.raises(SystemExit):
        cli.main(["--provider", "fake", "--fault", "nope", "idea"])
