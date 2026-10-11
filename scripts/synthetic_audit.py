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


def _pct(x):
    return "%+.2f%%" % (100 * x)


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
    # Promising on the base rules (positive lower bounds), so the F2 rule below is a downgrade that applies.
    base = _backtest(rng, "base", 0.009, 0.0041)
    base["validation"].update(n=212, blocks=19, ci_low=0.0006)
    base["baseline"]["paired_ci_low"] = 0.0003
    val, train = base["validation"], base["train"]
    w.emit("backtest_result", "mathematician", base, gap=3.5)
    w.emit("agent_finished", "mathematician", {"step": "backtest", "status": "ok", "duration_ms": 4200,
           "summary": "base run done"})
    w.emit("agent_started", "naysayer", {"step": "critique_1"})
    # The 7 coded checks, notes worded like src/auditor/checks.py.
    for check, passed, value, note in (
            ("evidence", True, {"n": val["n"], "blocks": val["blocks"]},
             "validation needs n >= 30 and at least 6 distinct 10-trading-day blocks"),
            ("leakage", True, "2026-06-30", "no feature or trade date after 2026-06-30 (earnings features exempt, see caveat)"),
            ("decay", False, {"train_mean": train["mean"], "validation_mean": val["mean"]},
             "validation mean %s vs train mean %s" % (_pct(val["mean"]), _pct(train["mean"]))),
            ("shared_window", True, 0, "0 earlier audit(s) used this validation window. About 5% of plans with no "
             "real edge pass this test by chance; testing many variants of one idea raises that."),
            ("cost_realism", True, None, "stock_long: no fees or slippage modeled"),
            ("tail_risk", True, {"worst_trade": train["worst_trade"], "worst_window": train["worst_window"]},
             "worst trade %s, worst 10-day window %s (train plus validation)"
             % (_pct(train["worst_trade"]), _pct(train["worst_window"]))),
            ("data_drops", True, {}, "setups dropped for exits past the cutoff or the data, stale implied vol, "
             "missing earnings coverage")):
        w.emit("check_result", "naysayer", {"check": check, "passed": passed, "value": value, "note": note})
    w.emit("llm_call", "naysayer", _llm(rng, "deepseek-reasoner"))
    # M2 contract: followup_requested for each pick, then a backtest_result with run F* carrying title, result,
    # downgrade (the follow-up's rule was met) and cause.
    picks = (("F1", "dip entries cluster around earnings gaps"),
             ("F2", "validation is one regime; train years may disagree"),
             ("F4", "a single mega-cap may carry the validation profit"))
    for fid, reason in picks:
        w.emit("followup_requested", "naysayer", {"followup": fid, "reason": reason})
    w.emit("agent_finished", "naysayer", {"step": "critique_1", "status": "ok", "duration_ms": 6000,
           "summary": {"doubts": ["decay out of sample"], "followups": [f for f, _ in picks]}})
    w.emit("agent_started", "mathematician", {"step": "followups"})
    total = val["mean"] * val["n"]
    f2_cause = ("F2 per-year stability: the yearly train mean has the opposite sign to the validation mean "
                "in more than half the train years")
    runs = (("F1", "Earnings excluded", 173, 0.0033,
             "validation mean +0.33% over 173 trades (39 left out: earnings in the holding window; 0: no earnings coverage)",
             None),
            ("F2", "Per-year stability", val["n"], val["mean"],
             "train mean has the opposite sign to the validation mean (%s) in 7 of 12 train years" % _pct(val["mean"]),
             f2_cause),
            ("F4", "Concentration", 201, round((total - 0.098) / 201, 5),
             "without the top-contributing ticker (+9.80%% of the %s summed validation return): validation mean %s "
             "over 201 trades" % (_pct(total), _pct((total - 0.098) / 201)), None))
    for fid, title, n, mean, result, cause in runs:
        bt = _backtest(rng, fid, 0.009, mean)
        bt["validation"].update(n=n, mean=mean)
        bt.update(title=title, result=result, downgrade=cause is not None, cause=cause)
        w.emit("backtest_result", "mathematician", bt)
    w.emit("agent_finished", "mathematician", {"step": "followups", "status": "ok", "duration_ms": 5100,
           "summary": "F1, F2, F4 done"})
    w.emit("agent_started", "naysayer", {"step": "critique_2"})
    w.emit("llm_call", "naysayer", _llm(rng, "deepseek-reasoner"))
    w.emit("agent_finished", "naysayer", {"step": "critique_2", "status": "ok", "duration_ms": 5000,
           "summary": "final critique: the edge is not stable across train years"})
    w.emit("verdict", None, {"verdict": "inconclusive", "reason": "promising on the base rules, downgraded: " + f2_cause,
           "headline": {"n": val["n"], "mean": val["mean"], "ci_low": val["ci_low"],
                        "paired_ci_low": base["baseline"]["paired_ci_low"]},
           "downgrades": [{"cause": f2_cause, "from": "promising", "to": "inconclusive"}]}, gap=1.0)
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
