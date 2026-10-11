"""Report template (AUDITOR_SPEC section 9). Code writes every number, the verdict, caveats and the
disclaimer; the Reporter's prose is optional and checked against a banned-phrase list."""
import json
from pathlib import Path

from .checks import FIVE_PCT_LINE
from .plan import canonical
from .universe import GROUPS

BANNED = ("will profit", "guaranteed", "risk-free", "we recommend", "you should buy", "you should sell", "sure thing")
SUBTITLES = {"promising": "Passed a 6-month historical screen. Not a forecast. Not financial advice.",
             "inconclusive": "inconclusive: a strategy with no real edge lands here about half the time"}
LABELS = {"kill": "KILLED", "inconclusive": "INCONCLUSIVE", "promising": "PROMISING", "cannot_audit": "CANNOT AUDIT"}
EARNINGS_CAVEAT = ("Earnings caveat: actual report dates are used; companies usually announce dates weeks ahead, "
                   "so the look-ahead is small but not zero.")
FOOTER = ("Not financial advice. Survivorship bias: the universe is today's large caps. One validation window "
          "(2026-01-01 to 2026-06-30) shared by every audit. Costs are approximated (no fees for stocks; "
          "straddle costs from an ATM formula with haircuts). No position sizing is given.")


def prose_ok(text):
    low = (text or "").lower()
    return not any(b in low for b in BANNED)


def pct(x):
    return "n/a" if x is None else "%+.2f%%" % (100 * x)


def _stats_row(label, s):
    if not s:
        return "| %s | – | – | – | – | – | – | – |" % label
    return "| %s | %d | %d | %.0f%% | %s | %s | [%s, %s] | %s / %s |" % (
        label, s["n"], s["blocks"], 100 * s["win_rate"], pct(s["mean"]), pct(s["median"]), pct(s["ci_low"]), pct(s["ci_high"]),
        pct(s["worst_trade"]), pct(s["worst_window"]))


def render(ctx):
    v = ctx["verdict"]
    plan = ctx["plan"]
    label = LABELS.get(v["verdict"], v["verdict"].upper())
    lines = ["# Strategy Auditor report: %s" % label, "", ctx["what_tested"], "",
             "## 1. What was tested and the verdict", "",
             "**Verdict: %s.** %s" % (label, v["reason"])]
    if v["verdict"] in SUBTITLES:
        lines.append("")
        lines.append("*%s*" % SUBTITLES[v["verdict"]])
    if ctx.get("small_group_note"):
        lines += ["", "Note: %s." % ctx["small_group_note"]]
    if ctx.get("fake_llm"):
        lines += ["", "**FAKE LLM run (development only): the plan and critique were produced by keyword rules, not a model.**"]
    if ctx.get("budget_hit"):
        lines += ["", "The LLM call cap (7 calls for the Planner and Naysayer) was hit; the verdict rests on the evidence gathered so far."]
    h = v.get("headline") or {}
    if h:
        lines += ["", "Headline: validation n = %s, mean per trade %s, lower bound %s, paired lower bound vs baseline %s."
                  % (h.get("n", "–"), pct(h.get("mean")), pct(h.get("ci_low")), pct(h.get("paired_ci_low")))]

    lines += ["", "## 2. Idea, plan v0, assumptions", "", "Idea: %s" % ctx["idea"], "",
              "Plan v0 (frozen before any backtest), SHA-256 `%s`:" % ctx["plan_hash"], "", "```json",
              json.dumps(plan, indent=2, sort_keys=True), "```", ""]
    if plan.get("refused"):
        lines.append("Refused: %s" % plan.get("reason", ""))
    else:
        lines.append("Assumptions: " + ("; ".join(plan.get("assumptions") or []) or "none stated") + ".")
        lines.append("Not tested: " + ("; ".join(plan.get("not_tested") or []) or "nothing") + ".")
        if plan.get("universe_group") in GROUPS:
            lines.append("Universe: %s = %s." % (plan["universe_group"], ", ".join(GROUPS[plan["universe_group"]])))

    cov, drops = ctx.get("coverage") or {}, ctx.get("drops") or {}
    lines += ["", "## 3. Data coverage", ""]
    if cov:
        rows = cov.get("rows_per_ticker_year") or {}
        if rows:
            years = sorted({y for r in rows.values() for y in r})
            lines += ["| Ticker | " + " | ".join(years) + " |", "|---|" + "---|" * len(years)]
            lines += ["| %s | %s |" % (t, " | ".join(str(r.get(y, 0)) for y in years)) for t, r in rows.items()]
            lines.append("")
        lines.append("Skipped tickers (under 200 rows): %s." % (", ".join(cov.get("skipped") or []) or "none"))
        if cov.get("iv_range"):
            lines.append("Implied vol rows: %d, %s to %s." % (cov["iv_rows"], *cov["iv_range"]))
        first = cov.get("earnings_first_date") or {}
        if first:
            lines.append("Earliest earnings date per ticker: " + ", ".join("%s %s" % kv for kv in sorted(first.items())) + ".")
        if cov.get("tickers_without_earnings"):
            lines.append("No earnings coverage: %s (NaN earnings features; left out of F1)." % ", ".join(cov["tickers_without_earnings"]))
    for split in ("train", "validation"):
        d = drops.get(split)
        if d:
            lines.append("Dropped %s setups: %s." % (split, ", ".join("%s %d" % kv for kv in d.items())))
    if ctx.get("earnings_caveat"):
        lines += ["", EARNINGS_CAVEAT]

    lines += ["", "## 4. Results", "",
              "| Run | n | blocks | win | mean | median | 95% interval | worst trade / 10-day window |",
              "|---|---|---|---|---|---|---|---|"]
    base, bl = ctx.get("base") or {}, ctx.get("baseline") or {}
    lines.append(_stats_row("v0 train", base.get("train")))
    lines.append(_stats_row("v0 validation", base.get("validation")))
    lines.append(_stats_row("no-condition baseline, train", bl.get("train")))
    lines.append(_stats_row("no-condition baseline, validation", bl.get("validation")))
    rb = ctx.get("random_baseline") or {}
    if rb:
        lines.append(_stats_row("random selection at the same rate, validation (reported only)", rb.get("validation")))
    if ctx.get("stricter"):
        lines.append(_stats_row("stricter cost (+10% buyer / -10% seller), validation", ctx["stricter"].get("validation")))
    lines += ["", "Paired lower bound (v0 minus baseline, validation, 2.5th percentile): %s." % pct(bl.get("paired_ci_low"))]
    tail = ctx.get("tail") or {}
    if tail:
        extra = ""
        if "worst_trade_premiums" in tail:
            extra = " Seller losses: worst trade %.1f average premiums (%s of stock price); worst window %s vs total validation gain %s." % (
                tail["worst_trade_premiums"], pct(tail.get("worst_trade_pct")), pct(tail["worst_window"]),
                pct((tail.get("worst_window_vs_gain") or {}).get("validation_total_gain")))
        lines.append("Tail risk (train plus validation): worst trade %s, worst 10-trading-day window %s.%s" % (
            pct(tail.get("worst_trade")), pct(tail.get("worst_window")), extra))

    lines += ["", "## 5. Coded checks and follow-ups", "", "| Check | Passed | Note |", "|---|---|---|"]
    lines += ["| %s | %s | %s |" % (c["check"], "yes" if c["passed"] else "no", c["note"]) for c in ctx.get("checks") or []]
    fus = ctx.get("followups") or []
    lines += ["", "Follow-ups: " + ("none run (M1)" if not fus else "")]
    for f in fus:
        lines.append("- %s: %s. Result: %s. %s" % (f["id"], f["reason"], f.get("result", "n/a"),
                                                 ("Downgrade: %s" % f["downgrade"]) if f.get("downgrade") else "No downgrade."))
    if v.get("downgrades"):
        lines += ["", "Downgrades: " + "; ".join(d["cause"] for d in v["downgrades"]) + "."]

    lines += ["", "## 6. Shared validation window", "",
              "%d audit(s) have used this validation window before this one. %s" % (ctx.get("window_count", 0), FIVE_PCT_LINE)]

    lines += ["", "## 7. Naysayer critique and Reporter prose", "", "Naysayer: %s" % (ctx.get("critique") or "n/a")]
    if ctx.get("prose"):
        lines += ["", "Reporter: %s" % ctx["prose"]]
    else:
        lines += ["", "Reporter prose: not included."]

    lines += ["", "## 8. Recoveries", ""]
    recs = ctx.get("recoveries") or []
    lines += ["- [%s] %s: %s" % ("INJECTED" if r.get("injected") else "REAL", r["failed"], r["action"]) for r in recs] or ["none"]

    cost = ctx.get("cost") or {}
    lines += ["", "## 9. Cost and trace", "",
              "LLM calls: %s (prompt tokens %s, completion tokens %s), cost $%.4f (upper bound). neatlogs trace: %s." % (
                  cost.get("calls", 0), cost.get("prompt_tokens", 0), cost.get("completion_tokens", 0), cost.get("usd", 0.0),
                  ctx.get("trace_id") or "none")]
    lines += ["", "## 10. Disclaimer", "", FOOTER, ""]
    return "\n".join(lines)


def append_registry(path, line):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(line, sort_keys=True) + "\n")


def registry_count(path):
    path = Path(path)
    if not path.is_file():
        return 0
    return sum(1 for l in path.read_text(encoding="utf-8").splitlines() if l.strip())


__all__ = ["render", "prose_ok", "append_registry", "registry_count", "canonical"]
