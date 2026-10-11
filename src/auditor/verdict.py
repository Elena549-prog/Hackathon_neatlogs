"""Verdict rules, in code (spec section 7). LLMs explain; they cannot change the verdict."""
from src.auditor.checks import MIN_BLOCKS, MIN_N
from src.auditor.plan import STRADDLES

INCONCLUSIVE_LINE = "inconclusive: a strategy with no real edge lands here about half the time"
PROMISING_SUBTITLE = "Passed a 6-month historical screen. Not a forecast. Not financial advice."


def cannot_audit(reason):
    return {"verdict": "cannot_audit", "reason": reason, "downgrades": []}


def decide(family, base, baseline, paired_low, stricter=None, tail=None, followups=()):
    """base, baseline: stats() output for v0 and the no-condition baseline. stricter: stats() under
    stricter costs (straddles). tail: tail_risk() output. followups: run_followup() results."""
    val, train = base["validation"], base["train"]
    if val["n"] < MIN_N or val["blocks"] < MIN_BLOCKS:
        return {"verdict": "inconclusive", "downgrades": [],
                "reason": "not enough evidence: validation n = %d (need %d), %d blocks (need %d)"
                % (val["n"], MIN_N, val["blocks"], MIN_BLOCKS)}
    if val["mean"] <= 0:
        return {"verdict": "kill", "downgrades": [],
                "reason": "enough evidence and the validation mean return per trade is %+.2f%% (0 or below)"
                % (100 * val["mean"])}
    failed = []
    if val["ci_low"] is None or val["ci_low"] <= 0:
        failed.append("lower bound of the validation mean is not above 0 (%s)" % _p(val["ci_low"]))
    if paired_low is None or paired_low <= 0:
        failed.append("not better than the no-condition baseline: paired lower bound %s" % _p(paired_low))
    bm = baseline["train"]["mean"]
    if train["mean"] is None or bm is None or train["mean"] <= bm:
        failed.append("train mean %s is not above the train baseline mean %s" % (_p(train["mean"]), _p(bm)))
    if family in STRADDLES:
        lo = stricter["validation"]["ci_low"] if stricter else None
        if lo is None or lo <= 0:
            failed.append("fails the stricter-cost check: lower bound %s with 10%% worse costs" % _p(lo))
    if failed:
        return {"verdict": "inconclusive", "downgrades": [], "reason": "; ".join(failed)}
    downgrades = []
    if tail and tail.get("downgrade"):
        downgrades.append({"cause": "tail risk", "detail": "; ".join(tail.get("reasons", []))})
    for f in followups:
        if f.get("downgrade"):
            downgrades.append({"cause": f["id"], "detail": f.get("note", "")})
    if downgrades:
        return {"verdict": "inconclusive", "downgrades": downgrades,
                "reason": "passed the screen but was downgraded: " + "; ".join(
                    "%s (%s)" % (d["cause"], d["detail"]) for d in downgrades)}
    return {"verdict": "promising", "downgrades": [],
            "reason": "validation lower bound %s, paired lower bound vs baseline %s"
            % (_p(val["ci_low"]), _p(paired_low))}


def _p(x):
    return "n/a" if x is None else "%+.2f%%" % (100 * x)
