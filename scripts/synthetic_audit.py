"""Write a SYNTHETIC audit (events.jsonl + report.md) for UI development only.

Every number here is made up with a seeded random generator. The idea text says so, so the
interface labels itself. Never copy this into results/audits/ and never record it for the demo.

Usage: python scripts/synthetic_audit.py [--out runs/audits] [--id synthetic-demo]
"""
import argparse
import datetime as dt
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.auditor.events import validate_event  # noqa: E402

IDEA = "SYNTHETIC FIXTURE: buy dips in an uptrend (not a real audit)"
STATS_FIELDS = ("n", "blocks", "win_rate", "mean", "median", "ci_low", "ci_high",
                "worst_trade", "worst_window")


class _Writer:
    def __init__(self, audit_id, rng):
        self.audit_id, self.rng = audit_id, rng
        self.seq = 0
        self.t = dt.datetime(2026, 10, 11, 12, 0, 0, tzinfo=dt.timezone.utc)
        self.lines = []

    def emit(self, type_, agent, payload, gap=None):
        self.seq += 1
        if self.seq > 1:
            self.t += dt.timedelta(seconds=gap if gap is not None else self.rng.uniform(0.2, 3.5))
        event = {"seq": self.seq, "ts": self.t.isoformat().replace("+00:00", "Z"),
                 "audit_id": self.audit_id, "type": type_, "agent": agent, "payload": payload}
        problems = validate_event(event)
        assert not problems, problems
        self.lines.append(json.dumps(event))
        return event


def _stats(rng, mean):
    n = rng.randint(40, 260)
    sd = abs(mean) * 3 + 0.01
    return {"n": n, "blocks": rng.randint(6, 40), "win_rate": round(rng.uniform(0.35, 0.6), 3),
            "mean": round(mean, 5), "median": round(mean * 0.8, 5),
            "ci_low": round(mean - sd / n ** 0.5 * 2, 5), "ci_high": round(mean + sd / n ** 0.5 * 2, 5),
            "worst_trade": round(-rng.uniform(0.05, 0.2), 4), "worst_window": round(-rng.uniform(0.1, 0.4), 4)}


def _equity(rng, start, points, drift):
    day, total, out = dt.date.fromisoformat(start), 0.0, []
    for _ in range(points):
        while day.weekday() > 4:
            day += dt.timedelta(days=1)
        total += rng.gauss(drift, 0.02)
        out.append([day.isoformat(), round(total, 5)])
        day += dt.timedelta(days=rng.choice([1, 1, 2, 3]))
    return out


def _backtest(rng, run, drift_train, drift_val):
    train, val = _stats(rng, drift_train), _stats(rng, drift_val)
    base = _stats(rng, rng.uniform(-0.002, 0.004))
    base["paired_ci_low"] = round(val["mean"] - base["mean"] - 0.01, 5)
    edges = [round(-0.15 + i * 0.015, 3) for i in range(21)]
    return {"run": run, "train": train, "validation": val, "baseline": base,
            "equity_train": _equity(rng, "2015-01-02", 300, drift_train),
            "equity_validation": _equity(rng, "2026-01-02", 120, drift_val),
            "histogram": {"edges": edges, "counts": [rng.randint(0, 40) for _ in range(22)]}}


def _llm(rng, model="deepseek-chat"):
    p, c = rng.randint(900, 2500), rng.randint(150, 700)
    return {"model": model, "prompt_tokens": p, "completion_tokens": c,
            "cost_usd": round(p * 0.27e-6 + c * 1.1e-6, 6), "latency_ms": rng.randint(800, 4000)}


def write_synthetic_audit(dir, audit_id="synthetic-demo", seed=1):
    """Write dir/<audit_id>/events.jsonl and report.md; return the events path."""
    rng = random.Random(seed)
    w = _Writer(audit_id, rng)
    out = Path(dir) / audit_id
    out.mkdir(parents=True, exist_ok=True)
    plan = {"family": "stock_long", "universe_group": "all_50",
            "conditions": {"ret_5d": ["<", -0.03], "close_to_ma200": [">", 1.0]},
            "exit": {"target_pct": 0.05, "stop_pct": 0.03, "horizon_days": 10}}
    what = ("stock_long on all_50 (50 tickers): enter when ret_5d < -0.03 and close_to_ma200 > 1.0; "
            "exit at +5% / -3% / 10 days. Not tested: nothing.")

    w.emit("audit_started", None, {"idea": IDEA, "trace_id": "synthetic", "llm_budget": 8, "fault": None})
    w.emit("agent_started", "planner", {"step": "plan"})
    w.emit("llm_call", "planner", _llm(rng))
    w.emit("agent_finished", "planner", {"step": "plan", "status": "ok", "duration_ms": 3100,
           "summary": {"plan": plan, "plan_hash": "0" * 40 + "synthetic0000000000000001", "what_tested": what}})
    w.emit("agent_started", "researcher", {"step": "data"})
    for i, tool in enumerate(("get_prices", "get_earnings_dates", "build_features"), start=1):
        w.emit("tool_called", "researcher", {"tool": tool, "args": {"group": "all_50"}})
        if tool == "get_prices":
            w.emit("recovered", "researcher", {"failed": "dolthub timeout on a 14-day window",
                   "action": "halved the window and retried", "injected": True})
        w.emit("tool_result", "researcher", {"tool": tool, "ok": True, "duration_ms": rng.randint(300, 9000),
               "summary": "%s ok" % tool})
        w.emit("data_progress", "researcher", {"what": tool, "percent": 33 * i if i < 3 else 100})
    w.emit("agent_finished", "researcher", {"step": "data", "status": "ok", "duration_ms": 12000,
           "summary": {"coverage": "50 tickers, 2014-01-02 to 2026-07-29", "gaps": []}})
    w.emit("agent_started", "mathematician", {"step": "backtest"})
    w.emit("backtest_result", "mathematician", _backtest(rng, "base", 0.0012, -0.0008), gap=3.5)
    w.emit("agent_finished", "mathematician", {"step": "backtest", "status": "ok", "duration_ms": 4200,
           "summary": "base run done"})
    w.emit("agent_started", "naysayer", {"step": "critique_1"})
    w.emit("llm_call", "naysayer", _llm(rng, "deepseek-reasoner"))
    for check, passed, value, note in (("evidence", True, 120, "n >= 30 and >= 6 blocks"),
                                       ("leakage", True, 0, "no feature after the cutoff"),
                                       ("decay", False, -0.002, "validation mean below train mean")):
        w.emit("check_result", "naysayer", {"check": check, "passed": passed, "value": value, "note": note})
    w.emit("followup_requested", "naysayer", {"followup": "F2", "reason": "train years may disagree"})
    w.emit("followup_requested", "naysayer", {"followup": "F4", "reason": "one ticker may carry the result"})
    w.emit("agent_finished", "naysayer", {"step": "critique_1", "status": "ok", "duration_ms": 6000,
           "summary": "doubts: decay out of sample; asked for F2 and F4"})
    w.emit("agent_started", "mathematician", {"step": "followups"})
    for run in ("F2", "F4"):
        w.emit("backtest_result", "mathematician", _backtest(rng, run, 0.001, -0.001))
    w.emit("agent_finished", "mathematician", {"step": "followups", "status": "ok", "duration_ms": 5100,
           "summary": "F2, F4 done"})
    w.emit("agent_started", "naysayer", {"step": "critique_2"})
    w.emit("llm_call", "naysayer", _llm(rng, "deepseek-reasoner"))
    w.emit("agent_finished", "naysayer", {"step": "critique_2", "status": "ok", "duration_ms": 5000,
           "summary": "final critique: no edge out of sample"})
    base_event = next(json.loads(l) for l in w.lines if '"run": "base"' in l)
    val = base_event["payload"]["validation"]
    w.emit("verdict", None, {"verdict": "kill", "reason": "validation mean <= 0 with enough evidence",
           "headline": {"n": val["n"], "mean": val["mean"], "ci_low": val["ci_low"],
                        "paired_ci_low": base_event["payload"]["baseline"]["paired_ci_low"]},
           "downgrades": []}, gap=1.0)
    w.emit("agent_started", "reporter", {"step": "report"})
    w.emit("llm_call", "reporter", _llm(rng, "deepseek-flash"))
    report = out / "report.md"
    report.write_text("# Synthetic audit\n\nSynthetic fixture for UI development. Not a real audit.\n")
    w.emit("report_ready", "reporter", {"path": str(report), "trace_id": "synthetic", "prose_included": False})
    w.emit("agent_finished", "reporter", {"step": "report", "status": "ok", "duration_ms": 2500,
           "summary": "template report written"})
    path = out / "events.jsonl"
    path.write_text("\n".join(w.lines) + "\n")
    return path


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default="runs/audits")
    ap.add_argument("--id", default="synthetic-demo")
    args = ap.parse_args()
    print(write_synthetic_audit(Path(args.out), args.id))
