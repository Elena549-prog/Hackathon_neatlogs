"""report.md from a code template (spec section 9). Code writes the verdict, every number, the
caveats and the disclaimer; the Reporter's prose, if any, is only added as explanation."""
from src.auditor.data import VALID_END, VALID_START
from src.auditor.plan import GROUPS, STRADDLES, THIN_GROUPS, canonical, uses_earnings
from src.auditor.verdict import INCONCLUSIVE_LINE, PROMISING_SUBTITLE

STAMP = {"kill": "KILLED", "inconclusive": "INCONCLUSIVE", "promising": "PROMISING", "cannot_audit": "CANNOT AUDIT"}
FOOTER = ("Not financial advice. Universe: 50 of today's large caps (survivorship bias: companies that "
          "failed or shrank are missing). One 6-month validation window (%s to %s). Trading costs are "
          "approximated; stock trades model no fees." % (VALID_START, VALID_END))


def _pct(x):
    return "n/a" if x is None else "%+.2f%%" % (100 * x)


def _num(x, fmt="%.2f"):
    return "n/a" if x is None else fmt % x


def _row(name, s):
    if not s:
        return "| %s | n/a | | | | | | |" % name
    ci = "%s to %s" % (_pct(s["ci_low"]), _pct(s["ci_high"])) if s.get("ci_low") is not None else "n/a"
    return "| %s | %d | %d | %s | %s | %s | %s | %s |" % (
        name, s["n"], s["blocks"], ("%.1f%%" % (100 * s["win_rate"])) if s["win_rate"] is not None else "n/a",
        _pct(s["mean"]), ci, _pct(s["worst_trade"]), _pct(s["worst_window"]))


def render(state, earnings_caveat):
    v = state["verdict"]
    plan = state.get("plan_v0") or {}
    res = state.get("results") or {}
    out = ["# Strategy audit: %s" % STAMP[v["verdict"]], ""]

    # 1. what was tested, verdict
    if state.get("what_was_tested"):
        out += ["**What was tested:** %s" % state["what_was_tested"], ""]
    out += ["**Verdict: %s.** %s" % (v["verdict"], v["reason"])]
    if v["verdict"] == "promising":
        out += ["", "*%s*" % PROMISING_SUBTITLE]
    elif v["verdict"] == "inconclusive":
        out += ["", "*%s.*" % (INCONCLUSIVE_LINE[0].upper() + INCONCLUSIVE_LINE[1:])]
    for d in v.get("downgrades", []):
        out += ["- Downgraded by %s: %s" % (d["cause"], d["detail"])]
    out += [""]

    # 2. idea and plan
    out += ["## The idea and plan v0", "", "> %s" % state["idea"], ""]
    if plan:
        out += ["Plan v0 (frozen before any data or backtest), SHA-256 `%s`:" % state["plan_hash"], "",
                "```json", canonical(plan), "```", ""]
        if not plan["refuse"]["is_refused"]:
            out += ["- Hypothesis: %s" % plan["hypothesis"]]
            out += ["- Assumptions: %s" % ("; ".join(plan["assumptions"]) or "none")]
            out += ["- Not tested: %s" % ("; ".join(plan["not_tested"]) or "nothing")]
            if plan["universe_group"] in THIN_GROUPS:
                out += ["- Note: %s has only %d tickers; with one open trade per ticker, validation will usually "
                        "have too few trades for a verdict." % (plan["universe_group"], len(GROUPS[plan["universe_group"]]))]
            out += [""]

    if res.get("base"):
        # 3. data coverage
        cov, drops = res.get("coverage", {}), res.get("drops", {})
        out += ["## Data coverage", "",
                "- Tickers with prices: %d of %d%s" % (len(cov.get("tickers", {})), len(GROUPS[plan["universe_group"]]),
                                                      (" (missing: %s)" % ", ".join(cov["missing_prices"]))
                                                      if cov.get("missing_prices") else ""),
                "- Tickers with earnings dates: %s" % cov.get("earnings_covered"),
                "- Earliest earnings date per ticker: %s" % ", ".join(
                    "%s %s" % (t, c.get("earliest_earnings") or "none") for t, c in sorted(cov.get("tickers", {}).items())),
                "- Thin price history (fewer than 240 rows in some year 2015-2025): %s" % (", ".join(cov.get("gaps") or []) or "none"),
                "- Train setups dropped because their horizon ends in 2026: %d" % drops.get("train_exit_in_2026", 0),
                "- Validation setups dropped because their exit is past the data: %d" % drops.get("validation_exit_past_data", 0)]
        if plan["family"] in STRADDLES:
            out += ["- Straddle trades skipped for implied vol older than 5 days: %d" % drops.get("stale_iv", 0),
                    "- Straddle trades priced without earnings coverage: %d" % drops.get("earnings_unknown_cost", 0)]
        out += [""]

        # 4. results
        out += ["## Results", "",
                "| Run | Trades | 10-day blocks | Win rate | Mean per trade | 95% interval of mean | Worst trade | Worst 10-day window |",
                "|---|---|---|---|---|---|---|---|",
                _row("Plan v0, train", res["base"]["train"]), _row("Plan v0, validation", res["base"]["validation"]),
                _row("No-condition baseline, train", res["baseline"]["train"]),
                _row("No-condition baseline, validation", res["baseline"]["validation"]),
                _row("Random selection at the same rate, validation (reported only)", res["random"]["validation"])]
        if res.get("stricter"):
            out += [_row("Stricter costs (+10%), validation", res["stricter"]["validation"])]
        out += ["", "- Paired lower bound of (plan v0 minus no-condition baseline), validation: %s" % _pct(res["paired_low"])]
        tail = res.get("tail") or {}
        out += ["- Tail risk (train + validation): worst trade %s, worst 10-day window %s" % (
            _pct(tail.get("worst_trade")), _pct(tail.get("worst_window")))]
        if plan["family"] == "straddle_sell" and tail.get("worst_loss_premiums") is not None:
            out += ["- Straddle selling: worst loss %.1f average premiums (%.1f%% of the stock price); average premium "
                    "%.2f%% of price" % (tail["worst_loss_premiums"], tail["worst_loss_pct_price"], tail["avg_premium_pct_price"])]
        out += [""]

        # 5. checks and follow-ups
        out += ["## Coded checks", ""]
        for c in res.get("checks", []):
            out += ["- **%s**: %s. %s" % (c["check"], "pass" if c["passed"] else "flag", c["note"])]
        out += [""]
        if state.get("naysayer_1"):
            n1 = state["naysayer_1"]
            out += ["## Naysayer doubts and follow-ups", ""] + ["- %s" % d for d in n1["doubts"]]
            if n1.get("requested", 0) > len(n1["picked"]):
                out += ["- (The Naysayer asked for %d follow-ups; %d valid ones were run, the limit is 3.)"
                        % (n1["requested"], len(n1["picked"]))]
            out += [""]
            for f in state.get("followups", []):
                out += ["- **%s** (reason: %s): %s.%s" % (f["id"], f.get("reason") or "none", f["note"],
                                                          " Downgrade." if f["downgrade"] else "")]
            out += [""]
        if uses_earnings(plan) or any(f["id"] == "F1" for f in state.get("followups", [])):
            out += ["*Earnings caveat: %s*" % earnings_caveat, ""]

        # 6. shared window
        out += ["## Shared validation window", "",
                "%d audits have used the validation window %s to %s. About 5%% of plans with no real edge pass this "
                "test by chance; testing many variants of one idea raises that." % (
                    res.get("shared_window_audits", 1), VALID_START, VALID_END), ""]

    # 7. critique and prose
    if state.get("naysayer_2"):
        out += ["## Naysayer's final critique", "", state["naysayer_2"]["critique"], ""]
    if state.get("reporter_prose"):
        out += ["## Explanation", "", state["reporter_prose"], ""]

    # 8. recoveries
    if state.get("recoveries"):
        out += ["## Recoveries", ""]
        for r in state["recoveries"]:
            out += ["- [%s] %s: %s" % ("INJECTED" if r["injected"] else "REAL", r["failed"], r["action"])]
        out += [""]

    # 9. cost
    llm = state["llm"]
    out += ["## Cost of this audit", "",
            "- LLM calls: %d of 8 (non-Reporter %d of 7, Reporter %d)%s" % (
                llm["calls"], llm["nonreporter"], llm["reporter"],
                ". The 7-call cap was hit; the verdict uses the evidence so far" if llm.get("cap_hit") else ""),
            "- Tokens: %d prompt, %d completion" % (llm["prompt_tokens"], llm["completion_tokens"]),
            "- Cost: $%.4f (upper bound: peak, cache-miss prices)" % llm["cost_usd"],
            "- Audit ID / neatlogs trace: `%s`" % state["audit_id"], ""]
    if state.get("notes"):
        out += ["Notes: " + "; ".join(state["notes"]), ""]
    out += ["---", "", "*%s*" % FOOTER, ""]
    return "\n".join(out)
