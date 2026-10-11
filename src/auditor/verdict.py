"""Verdict rules (AUDITOR_SPEC section 7), in code. LLMs explain but cannot override."""

MIN_N, MIN_BLOCKS = 30, 6
CORE_REASON = "core of the idea not testable with available data"


def decide(results):
    """-> {"verdict", "reason", "headline", "downgrades"} from the orchestrator's results dict."""
    plan = results["plan"]
    if plan.get("refused"):
        return _out("cannot_audit", "refused")
    if plan.get("invalid_twice"):
        return _out("cannot_audit", "no valid plan")
    if plan.get("core_trigger_tested") is False:
        return _out("cannot_audit", CORE_REASON)

    val, train = results["base"]["validation"], results["base"]["train"]
    baseline = results["baseline"]
    headline = {"n": val["n"], "mean": val["mean"], "ci_low": val["ci_low"], "paired_ci_low": baseline.get("paired_ci_low")}
    if val["n"] < MIN_N:
        return _out("inconclusive", "not enough evidence: validation n < %d" % MIN_N, headline)
    if val["blocks"] < MIN_BLOCKS:
        return _out("inconclusive", "not enough evidence: trades fall in fewer than %d distinct 10-trading-day blocks" % MIN_BLOCKS, headline)
    if val["mean"] <= 0:
        return _out("kill", "validation mean <= 0 with enough evidence", headline)

    failed = []
    if not val["ci_low"] > 0:
        failed.append("lower bound of the validation mean is not above 0")
    paired = baseline.get("paired_ci_low")
    if paired is None or not paired > 0:
        failed.append("paired lower bound against the no-condition baseline is not above 0")
    if not train["mean"] > baseline["train"]["mean"]:
        failed.append("train mean is not above the train baseline mean")
    if plan["family"].startswith("straddle"):
        stricter = results.get("stricter") or {}
        s_val = stricter.get("validation") if stricter else None
        if not (s_val and s_val.get("ci_low", 0) > 0):
            failed.append("fails the stricter-cost check")
    if failed:
        return _out("inconclusive", "positive but not convincing: " + "; ".join(failed), headline)

    downgrades = []
    if results.get("tail", {}).get("fails"):
        downgrades.append({"cause": "tail risk", "from": "promising", "to": "inconclusive"})
    for d in results.get("followup_downgrades") or []:
        downgrades.append({"cause": d["cause"], "from": "promising", "to": "inconclusive"})
    if downgrades:
        return _out("inconclusive", "promising on the base rules, downgraded: " + "; ".join(d["cause"] for d in downgrades), headline, downgrades)
    return _out("promising", "all rules passed", headline)


def _out(verdict, reason, headline=None, downgrades=None):
    return {"verdict": verdict, "reason": reason, "headline": headline or {}, "downgrades": downgrades or []}
