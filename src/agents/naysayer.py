"""Naysayer: tries to kill every plan. A paper trade happens only if it approves."""
import json

from src.agents import DATA_NOTE
from src.agents.mathematician import MAX_SHARE, MIN_MATCHES

SYSTEM = (
    "You are the Naysayer on a paper-trading research team. Your job is to stop bad trades. "
    "Every trade has fixed levels: stop -3%, target +5%, 10 trading days; break-even is a 37.5% "
    "hit rate. The plan already passed a hard gate: at least 30 comparable past setups, no more "
    "than 80% of all past setups (so the conditions narrow something), and a cautious (95% lower "
    "bound) hit rate above 37.5%. Look for what the gate can't see: a thesis "
    "the cited facts don't support, conditions that don't express the thesis or look tuned to "
    "today's exact numbers, an edge too thin to trust (lower bound barely above 37.5%), and a "
    "thesis that doesn't fit a 10-day hold. Block if you find any real problem, and list each "
    "objection specifically enough for the Planner to fix it. Approve only if you have no "
    "objection; an approval lists no objections. " + DATA_NOTE
)

SCHEMA = {
    "type": "object",
    "properties": {
        "verdict": {"type": "string", "enum": ["approve", "block"]},
        "objections": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["verdict", "objections"],
    "additionalProperties": False,
}


def validate_verdict(out):
    """None if the output follows the rules, else the reason it doesn't."""
    if out.get("verdict") not in ("approve", "block"):
        return "verdict must be approve or block"
    if out["verdict"] == "approve" and out.get("objections"):
        return "approve must list no objections"
    if out["verdict"] == "block" and not out.get("objections"):
        return "block must list at least one objection"
    return None


def _gate(math):
    """(failure kind, objection) for the hard gate in SWARM_SPEC section 7, or (None, None) if it passes."""
    if math["n"] < MIN_MATCHES:
        return "too_few", "only %d comparable past setups match the conditions; need at least %d" % (math["n"], MIN_MATCHES)
    if math["n"] > MAX_SHARE * math["eligible"]:
        return "too_broad", ("thesis too broad: the conditions match %d of %d past setups (%.0f%%, limit %.0f%%); "
                             "narrow them so they pick out setups like this one"
                             % (math["n"], math["eligible"], 100 * math["match_share"], 100 * MAX_SHARE))
    if math["ev_per_share"] is None or math["ev_per_share"] <= 0:
        return "break_even", ("cautious hit rate %.1f%% (95%% lower bound; plain %.1f%% over %d setups) is not above "
                              "the 37.5%% break-even" % (100 * math["hit_rate_low"], 100 * math["hit_rate"], math["n"]))
    return None, None


def gate(math):
    """The hard gate, enforced in code. None if passed, else the objection."""
    return _gate(math)[1]


def retryable(math):
    """Worth a second round? Not when the thesis has enough evidence and it says the bet loses:
    rewording won't change that. Too few matches, too broad, and Naysayer objections are fixable."""
    return _gate(math)[0] != "break_even"


def run(llm, plan_view, facts, math, **tags):
    """-> (verdict, objections). Fails closed: anything invalid is a block."""
    objection = gate(math)
    if objection:
        return "block", [objection]     # no LLM call spent on a plan the gate already rejects
    view = {k: math[k] for k in ("n", "eligible", "match_share", "hit_rate", "hit_rate_low", "ev_pct", "conditions")}
    prompt = json.dumps({"plan": plan_view, "facts": facts, "math": view})
    out = llm("naysayer", SYSTEM, prompt, SCHEMA, **tags)
    err = validate_verdict(out)
    if err:
        return "block", ["invalid naysayer output: " + err]
    return out["verdict"], list(out["objections"])
