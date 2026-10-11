"""Audit orchestrator (AUDITOR_SPEC sections 4, 7, 8, 9, 16).

idea -> Planner (frozen plan v0) -> Researcher (data tools) -> Mathematician (backtest, baselines, statistics)
-> coded checks + one Naysayer critique -> verdict rules -> template report (+ optional Reporter prose).
Every step writes its result to state.json before the next starts; --resume continues from the last finished
step and never re-plans. Every UI element is driven by the events appended to events.jsonl.
"""
import datetime as dt
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd

from src.llm import LLMError

from . import agents, backtest, checks, report as report_mod, verdict as verdict_mod
from .data import build_features, coverage as coverage_of
from .eventlog import EventLog
from .plan import plan_hash, validate, what_tested
from .universe import ALL, GROUPS, MARKET, SMALL_GROUPS

LLM_BUDGET, NON_REPORTER_CAP = 8, 7
STEPS = ("plan", "data", "backtest", "critique", "verdict", "report")


class AuditError(Exception):
    pass


class BudgetExceeded(AuditError):
    pass


class State:
    def __init__(self, path, data):
        self.path, self.data = Path(path), data

    @classmethod
    def new(cls, path, audit_id, idea):
        return cls(path, {"audit_id": audit_id, "idea": idea, "created": _now(), "llm_calls": 0,
                          "cost": {"prompt_tokens": 0, "completion_tokens": 0, "usd": 0.0},
                          "recoveries": [], "injected_used": False, "steps": {}})

    @classmethod
    def load(cls, path):
        path = Path(path)
        if not path.is_file():
            raise AuditError("cannot resume: %s does not exist" % path)
        return cls(path, json.loads(path.read_text(encoding="utf-8")))

    def save(self):
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.data, indent=1, default=_json_default), encoding="utf-8")
        tmp.replace(self.path)

    def done(self, step):
        return self.data["steps"].get(step, {}).get("status") == "done"

    def result(self, step):
        return self.data["steps"][step]["result"]

    def finish(self, step, result):
        self.data["steps"][step] = {"status": "done", "result": result, "finished": _now()}
        self.save()


class Budget:
    """At most 8 llm() calls per audit; the 8th is reserved for the Reporter (section 8)."""

    def __init__(self, state):
        self.state = state

    def check(self, role):
        n = self.state.data["llm_calls"]
        if role != "reporter" and n >= NON_REPORTER_CAP:
            raise BudgetExceeded("LLM call cap: %d of %d non-Reporter calls used" % (n, NON_REPORTER_CAP))
        if n >= LLM_BUDGET:
            raise BudgetExceeded("LLM budget of %d calls exhausted" % LLM_BUDGET)

    def count(self):
        self.state.data["llm_calls"] += 1
        self.state.save()


def _now():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _json_default(v):
    if hasattr(v, "item"):
        return v.item()
    if hasattr(v, "isoformat"):
        return v.isoformat()
    return str(v)


def _clean(obj):
    """JSON round-trip so state and events hold plain Python values only."""
    return json.loads(json.dumps(obj, default=_json_default))


class Audit:
    def __init__(self, idea, audit_id, llm, tracer, root, cache_dir, fetchers, fault, resume, provider):
        self.audit_id, self.llm, self.tracer = audit_id, llm, tracer
        self.root, self.cache_dir, self.fetchers = Path(root), Path(cache_dir), fetchers
        self.fault, self.provider = fault, provider
        self.dir = self.root / audit_id
        self.dir.mkdir(parents=True, exist_ok=True)
        state_path = self.dir / "state.json"
        if resume:
            self.state = State.load(state_path)
            self.log = EventLog.resume(self.dir / "events.jsonl", audit_id)
        else:
            self.state = State.new(state_path, audit_id, idea)
            self.log = EventLog(self.dir / "events.jsonl", audit_id)
        self.idea = self.state.data["idea"]
        self.budget = Budget(self.state)
        self.step = "start"
        self.data = {}           # prices, market, features, iv, earnings (in memory only)
        tracer.on_span = self._on_span

    # ------------------------------------------------------------------ events from spans and recoveries
    def _on_span(self, rec):
        if rec.get("kind") != "llm":
            return
        agent = rec["name"]
        cost = self.state.data["cost"]
        cost["prompt_tokens"] += int(rec.get("prompt_tokens", 0))
        cost["completion_tokens"] += int(rec.get("completion_tokens", 0))
        cost["usd"] += float(rec.get("cost", 0.0))
        self.state.save()
        self.log.emit("llm_call", agent, {"model": rec.get("model"), "prompt_tokens": int(rec.get("prompt_tokens", 0)),
                                          "completion_tokens": int(rec.get("completion_tokens", 0)),
                                          "cost_usd": float(rec.get("cost", 0.0)),
                                          "latency_ms": int(1000 * float(rec.get("duration", 0.0)))})
        if int(rec.get("attempts", 1) or 1) > 1:
            self.recovered(agent, "empty or off-schema LLM reply from the %s" % agent, "retried the call once")

    def recovered(self, agent, failed, action):
        injected = self.fault is not None and not self.state.data.get("injected_used")
        if injected:
            self.state.data["injected_used"] = True
        entry = {"failed": failed, "action": action, "injected": injected}
        self.state.data["recoveries"].append(entry)
        self.state.save()
        self.log.emit("recovered", agent, entry)

    def call(self, role, fn, *args):
        self.budget.check(role)
        self.budget.count()
        return fn(self.llm, *args)

    def agent(self, name, step):
        """Context manager emitting agent_started / agent_finished with a summary set by the caller."""
        audit = self

        class _Ctx:
            def __enter__(self_):
                self_.t0, self_.summary = time.time(), None
                audit.log.emit("agent_started", name, {"step": step})
                return self_

            def __exit__(self_, exc_type, exc, tb):
                audit.log.emit("agent_finished", name, {"step": step, "status": "error" if exc else "ok",
                                                        "duration_ms": int(1000 * (time.time() - self_.t0)),
                                                        "summary": _clean(self_.summary) if self_.summary is not None else None})
                return False

        return _Ctx()

    # ------------------------------------------------------------------------------------------- steps
    def run(self):
        if "started" not in self.state.data:
            self.log.emit("audit_started", None, {"idea": self.idea, "trace_id": getattr(self.tracer, "trace_id", None),
                                                  "llm_budget": LLM_BUDGET, "fault": self.fault, "provider": self.provider})
            self.state.data["started"] = _now()
            self.state.save()
        try:
            self.step = "plan"
            if not self.state.done("plan"):
                self.step_plan()
            plan = self.state.result("plan")["plan"]
            cannot = bool(plan.get("refused") or plan.get("invalid_twice") or plan.get("core_trigger_tested") is False)
            if not cannot:
                self.step = "data"
                self.step_data()
                self.step = "backtest"
                if not self.state.done("backtest"):
                    self.step_backtest()
                self.step = "critique"
                if not self.state.done("critique"):
                    self.step_critique()
            self.step = "verdict"
            if not self.state.done("verdict"):
                self.step_verdict(cannot)
            self.step = "report"
            if not self.state.done("report"):
                self.step_report()
        except checks.LeakageError as e:
            self.log.emit("error", None, {"step": self.step, "message": "leakage check failed: %s" % e})
            raise AuditError("leakage check failed: %s" % e) from e
        except Exception as e:
            self.log.emit("error", None, {"step": self.step, "message": "%s: %s" % (type(e).__name__, e)})
            raise
        v = self.state.result("verdict")
        return {"verdict": v, "report_path": str(self.dir / "report.md"), "events_path": str(self.dir / "events.jsonl"),
                "state": self.state.data}

    def step_plan(self):
        with self.agent("planner", "plan") as a:
            raw = self.call("planner", agents.run_planner, self.idea, None)
            raws = [raw]
            plan, err = validate(raw)
            errors = []
            if err:
                errors.append(err)
                raw2 = self.call("planner", agents.run_planner, self.idea, err)
                raws.append(raw2)
                plan, err2 = validate(raw2)
                if err2:
                    errors.append(err2)
                    plan = {"refused": False, "invalid_twice": True, "errors": errors}
            frozen = _clean(plan)
            result = {"plan": frozen, "hash": plan_hash(frozen), "raw_replies": _clean(raws), "errors": errors,
                      "what_tested": what_tested(frozen) if not frozen.get("invalid_twice") else "no valid plan"}
            a.summary = {"plan": frozen, "plan_hash": result["hash"], "what_tested": result["what_tested"]}
        self.state.finish("plan", result)

    def _tool(self, name, args, fn):
        self.log.emit("tool_called", "researcher", {"tool": name, "args": args})
        t0 = time.time()
        try:
            out = fn()
        except Exception as e:
            self.log.emit("tool_result", "researcher", {"tool": name, "ok": False, "duration_ms": int(1000 * (time.time() - t0)),
                                                       "summary": "%s: %s" % (type(e).__name__, e)})
            raise
        self.log.emit("tool_result", "researcher", {"tool": name, "ok": True, "duration_ms": int(1000 * (time.time() - t0)),
                                                   "summary": out[1]})
        return out[0]

    def step_data(self):
        plan = self.state.result("plan")["plan"]
        tickers = GROUPS[plan["universe_group"]]
        straddle = plan["family"].startswith("straddle")
        quiet = self.state.done("data")             # on resume: reload data without replaying the events
        emit = (lambda *a, **k: None) if quiet else self.log.emit
        ctx = self.agent("researcher", "data") if not quiet else None
        if ctx:
            ctx.__enter__()
        try:
            def tool(name, args, fn):
                return fn()[0] if quiet else self._tool(name, args, fn)

            def get_prices():
                prices, skipped = self.fetchers["prices"](tickers, self.cache_dir)
                return (prices, skipped), "%d tickers with prices, %d skipped" % (len([t for t in prices if t not in MARKET]), len(skipped))

            prices, skipped = tool("get_prices", {"group": plan["universe_group"], "tickers": len(tickers)}, get_prices)
            emit("data_progress", "researcher", {"what": "prices", "percent": 33})

            def get_earnings():
                e = self.fetchers["earnings"]([t for t in tickers if t in prices], self.cache_dir)
                return e, "earnings dates for %d tickers" % sum(1 for v in e.values() if v)

            earnings = tool("get_earnings_dates", {"tickers": len(tickers)}, get_earnings)
            emit("data_progress", "researcher", {"what": "earnings", "percent": 66})
            iv = None
            if straddle:
                def get_iv():
                    # One fetch for all 50 tickers: DoltHub is queried per date window, so the cost is the same
                    # whatever the group, and the cache then serves every later audit.
                    df = self.fetchers["iv"](ALL, self.cache_dir,
                                             on_recovered=lambda f, a: self.recovered("researcher", f, a),
                                             fault_first_timeout=(self.fault == "dolthub_timeout"))
                    df = df[df["ticker"].isin([t for t in tickers if t in prices])]
                    return df, "%d implied-vol rows" % len(df)

                iv = tool("get_implied_vol", {"tickers": len(tickers)}, get_iv)
            market = {m: prices[m] for m in MARKET if m in prices}
            universe = {t: df for t, df in prices.items() if t not in MARKET}

            def features():
                f = build_features(universe, market, iv, earnings)
                return f, "%d ticker-days with features" % len(f)

            feats = tool("build_features", {"tickers": len(universe)}, features)
            emit("data_progress", "researcher", {"what": "features", "percent": 100})
            cov = coverage_of(universe, skipped, iv, earnings)
            self.data.update(prices=universe, market=market, features=feats, iv=iv, earnings=earnings, coverage=cov)
            if ctx:
                ctx.summary = {"coverage": {"tickers": len(universe), "skipped": skipped,
                                            "iv_rows": cov["iv_rows"], "tickers_without_earnings": cov["tickers_without_earnings"]}}
        except Exception:
            if ctx:
                ctx.__exit__(*__import__("sys").exc_info())
            raise
        if ctx:
            ctx.__exit__(None, None, None)
        if not quiet:
            self.state.finish("data", {"coverage": _clean(cov)})

    def step_backtest(self):
        plan = self.state.result("plan")["plan"]
        d = self.data
        prices, feats, earnings = d["prices"], d["features"], d["earnings"]
        calendar = d["market"]["SPY"].index
        with self.agent("mathematician", "backtest") as a:
            base, drops, trades = {}, {}, {}
            for split in ("train", "validation"):
                t, dr = backtest.run_backtest(prices, feats, plan, earnings, split)
                trades[split], drops[split] = t, dr
                base[split] = checks.stats(t, calendar)
            setups_val = backtest.select_setups(feats, plan, "validation")
            checks.assert_no_leakage(setups_val["date"])
            for t in trades.values():
                checks.assert_no_leakage(t["entry_date"])
            dates_max = max([setups_val["date"].max()] + [t["entry_date"].max() for t in trades.values() if len(t)]) if len(setups_val) else None

            no_cond = dict(plan, conditions={})
            bl_trades = {s: backtest.run_backtest(prices, feats, no_cond, earnings, s)[0] for s in ("train", "validation")}
            baseline = {s: checks.stats(bl_trades[s], calendar) for s in bl_trades}
            baseline["paired_ci_low"] = checks.paired_lower_bound(trades["validation"]["entry_date"], trades["validation"]["ret"],
                                                                  bl_trades["validation"]["entry_date"], bl_trades["validation"]["ret"], calendar)
            rate = len(trades["validation"]) / len(bl_trades["validation"]) if len(bl_trades["validation"]) else 0.0
            rng = np.random.default_rng(0)
            rand = {s: checks.stats(bl_trades[s][rng.random(len(bl_trades[s])) < rate], calendar) for s in bl_trades}

            stricter = None
            if plan["family"].startswith("straddle"):
                st = {s: backtest.run_backtest(prices, feats, plan, earnings, s, stricter=True)[0] for s in ("train", "validation")}
                stricter = {s: checks.stats(st[s], calendar) for s in st}
            all_trades = pd.concat([trades["train"], trades["validation"]], ignore_index=True)
            tail = checks.tail_risk(all_trades, plan["family"], float(trades["validation"]["ret"].sum()), calendar)

            payload = {"run": "base", "train": base["train"], "validation": base["validation"],
                       "baseline": dict(baseline["validation"], paired_ci_low=baseline["paired_ci_low"]),
                       "equity_train": checks.equity_curve(trades["train"]),
                       "equity_validation": checks.equity_curve(trades["validation"]),
                       "histogram": checks.histogram(all_trades["ret"])}
            self.log.emit("backtest_result", "mathematician", _clean(payload))
            if stricter:
                self.log.emit("backtest_result", "mathematician", _clean({
                    "run": "stricter_cost", "train": stricter["train"], "validation": stricter["validation"],
                    "baseline": payload["baseline"], "equity_train": [], "equity_validation": [], "histogram": {}}))
            result = {"base": base, "baseline": baseline, "random_baseline": rand, "stricter": stricter, "tail": tail,
                      "drops": drops, "dates_max": dates_max.date().isoformat() if dates_max is not None else None,
                      "n_trades": {s: int(len(t)) for s, t in trades.items()}}
            a.summary = {"validation_n": base["validation"]["n"], "validation_mean": base["validation"]["mean"]}
        self.state.finish("backtest", _clean(result))

    def _results(self):
        plan_r = self.state.result("plan")
        r = {"plan": plan_r["plan"], "what_tested": plan_r["what_tested"], "coverage": self.state.result("data")["coverage"]
             if self.state.done("data") else {}}
        r.update(self.state.result("backtest"))
        r["followup_downgrades"] = []
        if self.state.done("critique"):
            r["checks"] = self.state.result("critique")["checks"]
        return r

    def step_critique(self):
        results = self._results()
        window_count = report_mod.registry_count(self.root / "registry.jsonl")
        coded = checks.coded_checks(results, window_count)
        with self.agent("naysayer", "critique") as a:
            for c in coded:
                self.log.emit("check_result", "naysayer", _clean(c))
            results["checks"] = coded
            budget_hit, critique, doubts = False, "", []
            try:
                out = self.call("naysayer", agents.run_naysayer, agents.naysayer_context(results))
                critique, doubts = out["critique"], out["doubts"]
            except BudgetExceeded as e:
                budget_hit, critique = True, "LLM call cap hit before the critique: %s" % e
            except LLMError as e:
                critique = "Naysayer call failed: %s" % e
            a.summary = {"doubts": doubts, "critique": critique}
        self.state.finish("critique", {"checks": _clean(coded), "critique": critique, "doubts": doubts,
                                       "budget_hit": budget_hit, "window_count": window_count})

    def step_verdict(self, cannot):
        if cannot:
            results = {"plan": self.state.result("plan")["plan"]}
        else:
            results = self._results()
        v = verdict_mod.decide(results)
        self.log.emit("verdict", None, _clean(v))
        self.state.finish("verdict", _clean(v))

    def step_report(self):
        plan_r, v = self.state.result("plan"), self.state.result("verdict")
        plan = plan_r["plan"]
        bt = self.state.result("backtest") if self.state.done("backtest") else {}
        cr = self.state.result("critique") if self.state.done("critique") else {}
        cost = self.state.data["cost"]
        group = plan.get("universe_group")
        ctx = {"idea": self.idea, "audit_id": self.audit_id, "plan": plan, "plan_hash": plan_r["hash"],
               "what_tested": plan_r["what_tested"], "verdict": v,
               "coverage": self.state.result("data")["coverage"] if self.state.done("data") else {},
               "drops": bt.get("drops", {}), "base": bt.get("base", {}), "baseline": bt.get("baseline", {}),
               "random_baseline": bt.get("random_baseline", {}), "stricter": bt.get("stricter"), "tail": bt.get("tail", {}),
               "checks": cr.get("checks", []), "followups": [], "window_count": cr.get("window_count", 0),
               "critique": cr.get("critique"), "prose": None, "recoveries": self.state.data["recoveries"],
               "cost": {"calls": self.state.data["llm_calls"], "prompt_tokens": cost["prompt_tokens"],
                        "completion_tokens": cost["completion_tokens"], "usd": cost["usd"]},
               "trace_id": getattr(self.tracer, "trace_id", None),
               "small_group_note": ("%s has %d tickers: usually inconclusive for lack of trades" % (group, len(GROUPS[group]))
                                    if group in SMALL_GROUPS else None),
               "earnings_caveat": any(f.startswith("earnings") or f == "days_since_earnings" for f in (plan.get("conditions") or {})),
               "fake_llm": self.provider == "fake", "budget_hit": bool(cr.get("budget_hit"))}
        with self.agent("reporter", "report") as a:
            prose = None
            if not plan.get("refused"):
                try:
                    text = self.call("reporter", agents.run_reporter, report_mod.render(ctx))
                    prose = text if report_mod.prose_ok(text) else None
                except (LLMError, BudgetExceeded):
                    prose = None
            ctx["cost"]["calls"] = self.state.data["llm_calls"]
            ctx["cost"].update({k: cost[k] for k in ("prompt_tokens", "completion_tokens", "usd")})
            ctx["prose"] = prose
            path = self.dir / "report.md"
            path.write_text(report_mod.render(ctx), encoding="utf-8")
            report_mod.append_registry(self.root / "registry.jsonl", {
                "date": _now()[:10], "audit_id": self.audit_id, "idea": self.idea, "family": plan.get("family"),
                "universe_group": group, "plan_hash": plan_r["hash"], "verdict": v["verdict"]})
            self.log.emit("report_ready", "reporter", {"path": str(path), "trace_id": getattr(self.tracer, "trace_id", None),
                                                      "prose_included": prose is not None})
            a.summary = {"prose_included": prose is not None}
        self.state.finish("report", {"path": str(path), "prose_included": prose is not None})


def run_audit(idea, audit_id, llm, tracer, *, root, cache_dir, fetchers, fault=None, resume=False, provider="deepseek"):
    """Run (or resume) one audit. Returns {"verdict", "report_path", "events_path", "state"}."""
    return Audit(idea, audit_id, llm, tracer, root, cache_dir, fetchers, fault, resume, provider).run()
