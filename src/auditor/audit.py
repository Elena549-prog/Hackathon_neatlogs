"""One audit, end to end (spec sections 4, 7, 8, 10, 16).

Steps: plan -> data -> backtest -> naysayer_1 -> followups -> naysayer_2 -> verdict -> report.
After each step, state.json is saved; --resume continues from the first unfinished step with the
next event seq. Plan v0 is frozen (JSON and SHA-256 hash in state.json) before any data fetch or
backtest and is never re-planned.

LLM budget: 8 calls per audit. The 8th is reserved for the Reporter; all other roles together may
use at most 7. Each llm() invocation counts as one call (internal retries don't), and the count is
persisted and checked before every call.
"""
import datetime as dt
import json
import os
import time
import uuid

import pandas as pd

from src.auditor import agents, backtest, checks, report, verdict as rules
from src.auditor.data import VALID_END, VALID_START, build_panel
from src.auditor.plan import (STRADDLES, THIN_GROUPS, canonical, normalize, plan_hash, to_map, uses_earnings,
                              validate, what_was_tested)

LLM_BUDGET = 8
NONREPORTER_CAP = LLM_BUDGET - 1
RUNS_DIR = os.path.join("runs", "audits")
REGISTRY = os.path.join(RUNS_DIR, "registry.jsonl")
STEPS = ("plan", "data", "backtest", "naysayer_1", "followups", "naysayer_2", "verdict", "report")
EARNINGS_CAVEAT = ("Actual earnings report dates are used; companies usually announce dates weeks ahead, "
                   "so the look-ahead is small but not zero.")


class BudgetExceeded(Exception):
    pass


def now():
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def new_id():
    return dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:6]


def _jsonable(x):
    if isinstance(x, dict):
        return {str(k): _jsonable(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_jsonable(v) for v in x]
    if hasattr(x, "item"):
        return x.item()
    if isinstance(x, (pd.Timestamp, dt.date)):
        return x.isoformat()
    if isinstance(x, float) and x != x:
        return None
    return x


def trace_id():
    """Current OpenTelemetry trace id as hex, or None without neatlogs."""
    try:
        from opentelemetry import trace
        ctx = trace.get_current_span().get_span_context()
        return "%032x" % ctx.trace_id if ctx.trace_id else None
    except Exception:
        return None


class Audit:
    def __init__(self, audit_id, llm, tracer, runs_dir=RUNS_DIR, fetch=None, cache_dir=None,
                 followups=True, use_reporter=True, sleep=time.sleep, registry=None):
        self.id = audit_id
        self.dir = os.path.join(runs_dir, audit_id)
        self.llm, self.tracer = llm, tracer
        self.fetch, self.cache_dir, self.sleep = fetch, cache_dir, sleep
        self.followups_on, self.use_reporter = followups, use_reporter
        self.registry = registry or os.path.join(runs_dir, "registry.jsonl")
        self.state = None
        self._panel = self._base_trades = None
        self.fault = [None]

    # ------------------------------------------------------------------------- state and events

    @property
    def state_path(self):
        return os.path.join(self.dir, "state.json")

    def save(self):
        tmp = self.state_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(_jsonable(self.state), f, indent=1)
        os.replace(tmp, self.state_path)

    def emit(self, type_, agent=None, **payload):
        ev = {"seq": self.state["seq"], "ts": now(), "audit_id": self.id, "type": type_, "agent": agent,
              "payload": _jsonable(payload)}
        self.state["seq"] += 1
        with open(os.path.join(self.dir, "events.jsonl"), "a", encoding="utf-8") as f:
            f.write(json.dumps(ev) + "\n")
        self.save()
        return ev

    def recovered(self, failed, action, injected, agent=None):
        self.state["recoveries"].append({"failed": failed, "action": action, "injected": bool(injected),
                                         "agent": agent})
        self.emit("recovered", agent, failed=failed, action=action, injected=bool(injected))

    # ------------------------------------------------------------------------------- the LLM

    def call(self, role, system, prompt, schema, step):
        llm = self.state["llm"]
        if role == "reporter":
            if llm["reporter"] >= 1:
                raise BudgetExceeded("the Reporter's call is used")
        elif llm["nonreporter"] >= NONREPORTER_CAP:
            llm["cap_hit"] = True
            self.save()
            raise BudgetExceeded("%d of %d non-Reporter LLM calls used" % (NONREPORTER_CAP, NONREPORTER_CAP))
        llm["calls"] += 1
        llm["reporter" if role == "reporter" else "nonreporter"] += 1
        self.save()                                    # persisted before the call
        before = len(self.tracer.spans)
        start = time.time()
        try:
            return self.llm(role, system, prompt, schema, audit_id=self.id, step=step)
        finally:
            spans = [s for s in self.tracer.spans[before:] if s["kind"] == "llm"]
            rec = spans[-1] if spans else {}
            llm["prompt_tokens"] += rec.get("prompt_tokens", 0)
            llm["completion_tokens"] += rec.get("completion_tokens", 0)
            llm["cost_usd"] += rec.get("cost", 0.0)
            self.emit("llm_call", role, model=rec.get("model"), prompt_tokens=rec.get("prompt_tokens", 0),
                      completion_tokens=rec.get("completion_tokens", 0), cost_usd=round(rec.get("cost", 0.0), 6),
                      latency_ms=int(1000 * (time.time() - start)))
            if rec.get("attempts", 1) > 1:
                injected = getattr(self.llm, "fault_fired", None) and self.llm.fault_fired.pop()
                self.recovered("empty or off-schema LLM reply (%s)" % role, "retried once", injected, role)

    # --------------------------------------------------------------------------------- running

    def start(self, idea, fault=None):
        os.makedirs(self.dir, exist_ok=True)
        self.state = {"audit_id": self.id, "idea": idea, "fault": fault, "created": now(), "seq": 0,
                      "done": [], "plan_v0": None, "plan_hash": None, "what_was_tested": None,
                      "results": {}, "followups": [], "naysayer_1": None, "naysayer_2": None,
                      "verdict": None, "recoveries": [], "notes": [],
                      "llm": {"calls": 0, "nonreporter": 0, "reporter": 0, "prompt_tokens": 0,
                              "completion_tokens": 0, "cost_usd": 0.0, "cap_hit": False}}
        self.fault = [fault]
        with self.tracer.span("workflow", "audit", audit_id=self.id):
            self.emit("audit_started", None, idea=idea, trace_id=trace_id(), llm_budget=LLM_BUDGET, fault=fault)
            self._run()
        return self.state

    def resume(self):
        with open(self.state_path, encoding="utf-8") as f:
            self.state = json.load(f)
        self.fault = [None]                            # an injected fault is not replayed on resume
        with self.tracer.span("workflow", "audit", audit_id=self.id, resumed="true"):
            self.state["notes"].append("resumed at %s after step %s" % (now(), (self.state["done"] or ["start"])[-1]))
            self._run()
        return self.state

    def _run(self):
        try:
            for step in STEPS:
                if step in self.state["done"]:
                    continue
                if self.state["verdict"] and step not in ("report",):
                    self._done(step)                   # cannot_audit skips straight to the report
                    continue
                getattr(self, "_step_" + step)()
                self._done(step)
        except Exception as e:
            self.emit("error", None, step=next((s for s in STEPS if s not in self.state["done"]), None),
                      message="%s: %s" % (type(e).__name__, e))
            self.tracer.flush()
            raise
        self.tracer.flush()

    def _done(self, step):
        self.state["done"].append(step)
        self.save()

    def _agent(self, agent, step):
        return _AgentStep(self, agent, step)

    # ----------------------------------------------------------------------------------- steps

    def _step_plan(self):
        idea, fix, plan, error = self.state["idea"], None, None, None
        with self._agent("planner", "plan") as a:
            for attempt in (1, 2):
                try:
                    raw = self.call("planner", agents.PLANNER_SYSTEM, agents.planner_prompt(idea, fix),
                                    agents.planner_schema(), "plan")
                    plan = to_map(raw)
                    error = validate(plan)
                except BudgetExceeded:
                    raise
                except Exception as e:          # LLMError, malformed conditions
                    plan, error = None, "%s: %s" % (type(e).__name__, e)
                if error is None:
                    break
                fix = error
                self.state["notes"].append("planner attempt %d invalid: %s" % (attempt, error))
            if error is not None:
                self._verdict(rules.cannot_audit("no valid plan after 2 attempts (%s)" % error))
                a.summary = {"invalid": error}
                return
            plan = normalize(plan)
            self.state["plan_v0"] = plan
            self.state["plan_hash"] = plan_hash(plan)
            self.save()                                # frozen before any data fetch or backtest
            if plan["refuse"]["is_refused"]:
                self._verdict(rules.cannot_audit("refused: " + plan["refuse"]["reason"]))
                a.summary = {"refused": plan["refuse"]["reason"], "hash": self.state["plan_hash"]}
                return
            self.state["what_was_tested"] = what_was_tested(plan)
            a.summary = {"plan_v0": plan, "hash": self.state["plan_hash"],
                         "what_was_tested": self.state["what_was_tested"]}
            if not plan["core_trigger_tested"]:
                self._verdict(rules.cannot_audit("core of the idea not testable with available data"))

    def panel(self):
        if self._panel is None:
            plan = self.state["plan_v0"]
            kw = {"fetch": self.fetch, "sleep": self.sleep,
                  "log": lambda t, ag, **p: self.emit(t, ag, **p),
                  "on_recovered": lambda failed, action, inj: self.recovered(failed, action, inj, "researcher"),
                  "fault": self.fault}
            if self.cache_dir:
                kw["cache_dir"] = self.cache_dir
            with self.tracer.span("tool", "build_panel", agent="researcher", audit_id=self.id, step="data") as rec:
                self._panel = build_panel(plan["family"], plan["universe_group"], **kw)
                rec["output"] = self._panel.coverage
        return self._panel

    def base_trades(self):
        if self._base_trades is None:
            self._base_trades = backtest.run(self.panel(), self.state["plan_v0"])[0]
        return self._base_trades

    def _step_data(self):
        with self._agent("researcher", "data") as a:
            if self.fault[0] == "dolthub_timeout" and self.state["plan_v0"]["family"] not in STRADDLES:
                self.state["notes"].append("fault dolthub_timeout not triggered: stock_long fetches no implied vol")
            p = self.panel()
            cov = dict(p.coverage)
            self.state["results"]["coverage"] = cov
            a.summary = {"tickers": len(p.frames), "missing_prices": cov["missing_prices"],
                         "earnings_covered": cov["earnings_covered"], "gaps": cov["gaps"]}

    def _tool(self, name, fn, **args):
        self.emit("tool_called", "mathematician", tool=name, args=args)
        start = time.time()
        with self.tracer.span("tool", name, agent="mathematician", audit_id=self.id, step="backtest", **{
                k: str(v) for k, v in args.items()}) as rec:
            out = fn()
            rec["output"] = {"trades": len(out[0])}
        self.emit("tool_result", "mathematician", tool=name, ok=True, duration_ms=int(1000 * (time.time() - start)),
                  summary={"trades": len(out[0])})
        return out

    def _step_backtest(self):
        plan, p = self.state["plan_v0"], self.panel()
        cal = p.calendar
        with self._agent("mathematician", "backtest") as a:
            trades, drops = self._tool("backtest", lambda: backtest.run(p, plan), run="base")
            self._base_trades = trades
            base_trades, _ = self._tool("backtest", lambda: backtest.run(p, plan, conditions={}), run="baseline")
            base = checks.stats(trades, cal)
            baseline = checks.stats(base_trades, cal)
            paired_low = checks.paired(trades, base_trades, cal)
            n_cond = len(trades) / len(base_trades) if len(base_trades) else 0
            rand_trades, _ = backtest.run(p, plan, random_rate=min(1.0, max(n_cond, 1e-6)), seed=0)
            res = self.state["results"]
            res.update({"base": base, "baseline": baseline, "paired_low": paired_low,
                        "random": checks.stats(rand_trades, cal), "drops": drops,
                        "tail": checks.tail_risk(plan["family"], trades, cal)})
            if plan["family"] in STRADDLES:
                st, _ = self._tool("backtest", lambda: backtest.run(p, plan, cost_bump=0.10), run="stricter_cost")
                res["stricter"] = checks.stats(st, cal)
                tr = trades
                res["earnings_cost_share"] = float((tr["earnings_in_window"] == 1).mean()) if len(tr) else None
            self.emit("backtest_result", "mathematician", run="base", train=base["train"], validation=base["validation"],
                      baseline={**baseline, "paired_low": paired_low},
                      equity_train=checks.equity_curve(trades, "train"),
                      equity_validation=checks.equity_curve(trades, "validation"),
                      histogram=checks.histogram(trades))
            if "stricter" in res:
                self.emit("backtest_result", "mathematician", run="stricter_cost", train=res["stricter"]["train"],
                          validation=res["stricter"]["validation"], baseline=None, equity_train=[],
                          equity_validation=[], histogram=None)
            self._coded_checks()
            a.summary = {"validation": base["validation"], "paired_low": paired_low}

    def _coded_checks(self):
        res, plan = self.state["results"], self.state["plan_v0"]
        val, train = res["base"]["validation"], res["base"]["train"]
        items = []
        items.append(("evidence", checks.evidence_ok(val), {"n": val["n"], "blocks": val["blocks"]},
                      "validation n >= %d and >= %d distinct 10-day blocks" % (checks.MIN_N, checks.MIN_BLOCKS)))
        items.append(("leakage", True, None, "no train outcome reaches 2026; no setup after %s; implied vol never "
                      "newer than its setup day%s" % (VALID_END, " (earnings features exempt: %s)" % EARNINGS_CAVEAT
                                                      if uses_earnings(plan) else "")))
        decay = None if val["mean"] is None or train["mean"] is None else val["mean"] - train["mean"]
        items.append(("out_of_sample_decay", decay is None or decay >= 0, {"train_mean": train["mean"],
                      "validation_mean": val["mean"]}, "validation mean vs train mean"))
        prior = self._registry_count()
        res["shared_window_audits"] = prior + 1
        items.append(("shared_window", True, prior + 1, "%d audits have used the validation window %s..%s. About 5%% "
                      "of plans with no real edge pass this test by chance; testing many variants of one idea "
                      "raises that." % (prior + 1, VALID_START, VALID_END)))
        if plan["family"] in STRADDLES:
            lo = res["stricter"]["validation"]["ci_low"]
            items.append(("cost_realism", lo is not None and lo > 0,
                          {"earnings_window_share": res.get("earnings_cost_share"), "stricter_ci_low": lo},
                          "share of trades priced x1.20 for earnings, and the lower bound with 10% worse costs"))
        tail = res["tail"]
        items.append(("tail_risk", not tail.get("downgrade"), {k: v for k, v in tail.items() if k != "reasons"},
                      "; ".join(tail.get("reasons", [])) or "worst trade and worst 10-day window on train + validation"))
        items.append(("data_drops", True, res["drops"], "setups dropped or skipped by the data rules"))
        res["checks"] = []
        for name, passed, value, note in items:
            res["checks"].append({"check": name, "passed": bool(passed), "value": value, "note": note})
            self.emit("check_result", "naysayer", check=name, passed=bool(passed), value=value, note=note)

    def _facts(self):
        res = self.state["results"]
        return {"what_was_tested": self.state["what_was_tested"], "plan_v0": self.state["plan_v0"],
                "train": res["base"]["train"], "validation": res["base"]["validation"],
                "no_condition_baseline": {"train": res["baseline"]["train"], "validation": res["baseline"]["validation"]},
                "paired_lower_bound_vs_baseline": res["paired_low"],
                "stricter_cost_validation": (res.get("stricter") or {}).get("validation"),
                "tail_risk": res["tail"], "checks": res["checks"]}

    def _step_naysayer_1(self):
        if not self.followups_on:
            self.state["notes"].append("follow-ups off (M1 run)")
            return
        with self._agent("naysayer", "naysayer_1") as a:
            try:
                out = self.call("naysayer", agents.NAYSAYER_SYSTEM_1, json.dumps(_jsonable(self._facts())),
                                agents.NAYSAYER_SCHEMA_1, "naysayer_1")
            except BudgetExceeded as e:
                self.state["notes"].append(str(e))
                return
            except Exception as e:
                self.state["notes"].append("naysayer call 1 failed: %s" % e)
                a.status = "error"
                return
            picked = checks.pick_followups(out.get("followups") or [], self.state["plan_v0"]["family"])
            self.state["naysayer_1"] = {"doubts": [str(d) for d in out.get("doubts") or []], "picked": picked,
                                        "requested": len(out.get("followups") or [])}
            a.summary = {"doubts": self.state["naysayer_1"]["doubts"]}

    def _step_followups(self):
        n1 = self.state.get("naysayer_1")
        if not n1 or not n1["picked"]:
            return
        plan, p = self.state["plan_v0"], self.panel()
        with self._agent("mathematician", "followups"):
            for f in n1["picked"]:
                if f["id"] in [r["id"] for r in self.state["followups"]]:
                    continue
                self.emit("followup_requested", "naysayer", followup=f["id"], reason=f["reason"])
                with self.tracer.span("tool", "followup", agent="mathematician", audit_id=self.id, step="followups",
                                      followup=f["id"]):
                    r = checks.run_followup(f["id"], p, plan, self.base_trades(), self.state["results"]["base"],
                                            backtest.run)
                r["reason"] = f["reason"]
                self.state["followups"].append(r)
                val = (r.get("result") or {}).get("validation")
                self.emit("backtest_result", "mathematician", run=f["id"], train=None, validation=val, baseline=None,
                          equity_train=[], equity_validation=[], histogram=None)
                self.emit("check_result", "naysayer", check=f["id"], passed=not r["downgrade"], value=None, note=r["note"])

    def _step_naysayer_2(self):
        if not self.state.get("naysayer_1"):
            return
        with self._agent("naysayer", "naysayer_2") as a:
            facts = dict(self._facts(), followups=self.state["followups"])
            try:
                out = self.call("naysayer", agents.NAYSAYER_SYSTEM_2, json.dumps(_jsonable(facts)),
                                agents.NAYSAYER_SCHEMA_2, "naysayer_2")
                self.state["naysayer_2"] = {"critique": str(out["critique"])}
                a.summary = {"critique": self.state["naysayer_2"]["critique"]}
            except BudgetExceeded as e:
                self.state["notes"].append(str(e))
            except Exception as e:
                self.state["notes"].append("naysayer call 2 failed: %s" % e)
                a.status = "error"

    def _step_verdict(self):
        res, plan = self.state["results"], self.state["plan_v0"]
        v = rules.decide(plan["family"], res["base"], res["baseline"], res["paired_low"], res.get("stricter"),
                         res["tail"], self.state["followups"])
        self._verdict(v)

    def _verdict(self, v):
        self.state["verdict"] = v
        res = self.state["results"]
        val = (res.get("base") or {}).get("validation") or {}
        self.emit("verdict", None, verdict=v["verdict"], reason=v["reason"], downgrades=v.get("downgrades", []),
                  headline={"n": val.get("n"), "mean": val.get("mean"), "ci_low": val.get("ci_low"),
                            "paired_low": res.get("paired_low")})

    def _step_report(self):
        with self._agent("reporter", "report") as a:
            prose = None
            if self.use_reporter:
                try:
                    out = self.call("reporter", agents.REPORTER_SYSTEM,
                                    json.dumps(_jsonable({"verdict": self.state["verdict"],
                                                          **(self._facts() if self.state["results"].get("base") else
                                                             {"idea": self.state["idea"]})})),
                                    agents.REPORTER_SCHEMA, "report")
                    text = str(out.get("prose", ""))
                    if agents.prose_ok(text):
                        prose = text
                    else:
                        self.state["notes"].append("Reporter prose dropped: it contained a banned phrase")
                except Exception as e:
                    self.state["notes"].append("Reporter call failed (%s); the template ships without prose" % e)
            self.state["reporter_prose"] = prose
            path = os.path.join(self.dir, "report.md")
            with open(path, "w", encoding="utf-8") as f:
                f.write(report.render(self.state, EARNINGS_CAVEAT))
            self._append_registry()
            a.summary = {"path": path, "prose_included": prose is not None}
        self.emit("report_ready", "reporter", path=path, trace_id=trace_id(), prose_included=prose is not None)

    # -------------------------------------------------------------------------------- registry

    def _registry_count(self):
        if not os.path.exists(self.registry):
            return 0
        with open(self.registry, encoding="utf-8") as f:
            lines = [json.loads(l) for l in f if l.strip()]
        return sum(1 for l in lines if l.get("verdict") != "cannot_audit" and l.get("audit_id") != self.id)

    def _append_registry(self):
        plan = self.state["plan_v0"] or {}
        line = {"date": now(), "audit_id": self.id, "idea": self.state["idea"], "family": plan.get("family"),
                "universe_group": plan.get("universe_group"), "plan_hash": self.state["plan_hash"],
                "verdict": self.state["verdict"]["verdict"]}
        os.makedirs(os.path.dirname(self.registry) or ".", exist_ok=True)
        with open(self.registry, "a", encoding="utf-8") as f:
            f.write(json.dumps(line) + "\n")


class _AgentStep:
    """agent_started / agent_finished events and an AGENT span around one step."""

    def __init__(self, audit, agent, step):
        self.audit, self.agent, self.step = audit, agent, step
        self.summary, self.status = None, "ok"

    def __enter__(self):
        self.t0 = time.time()
        self.span = self.audit.tracer.span("agent", self.agent, audit_id=self.audit.id, step=self.step)
        self.rec = self.span.__enter__()
        self.audit.emit("agent_started", self.agent, step=self.step)
        return self

    def __exit__(self, exc_type, exc, tb):
        status = "error" if exc_type else self.status
        self.rec["output"] = self.summary
        self.audit.emit("agent_finished", self.agent, step=self.step, status=status,
                        duration_ms=int(1000 * (time.time() - self.t0)),
                        summary=self.summary if not exc_type else {"error": str(exc)})
        self.span.__exit__(exc_type, exc, tb)
        return False
