"""Planner: decides why this setup is worth a paper trade, and revises when the Naysayer objects.

Levels are fixed by the label rule (+5% target, -3% stop, 10 trading days), so the swarm,
Laya, the backtest and the simulator all judge the same bet. The Planner supplies the
thesis and the conditions that describe setups like this one.
"""
import json

from src.agents import DATA_NOTE, FEATURE_GUIDE
from src.features import FEATURE_NAMES
from src.labels import HORIZON, STOP, TARGET
from src.tools import OPS

TOLERANCE = 0.01    # allowed difference between a plan's levels and the fixed ones
MIN_CONDITIONS, MAX_CONDITIONS = 1, 4

SYSTEM = (
    "You are the Planner on a paper-trading research team. Every trade has the same fixed "
    "levels: long at today's close (100), stop at 97 (-3%), target at 105 (+5%), exit after 10 "
    "trading days. It breaks even at a 37.5% hit rate. You decide why this setup is worth "
    "trading. Give a one-sentence thesis; 1 to 4 conditions on feature values that describe "
    "setups like this one (today's setup must satisfy them, and they are used to find comparable "
    "past setups, so they should express the thesis, not just copy today's numbers; conditions that "
    "match more than 80% of past setups are blocked as too broad, and fewer than 30 matches is "
    "too little evidence); and the fact "
    "keys your thesis relies on (only keys from the Researcher's facts). If objections from the "
    "Naysayer are given, revise so the plan answers each one. " + FEATURE_GUIDE + " " + DATA_NOTE
)

SCHEMA = {
    "type": "object",
    "properties": {
        "thesis": {"type": "string"},
        "conditions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"feature": {"type": "string", "enum": list(FEATURE_NAMES)},
                               "op": {"type": "string", "enum": list(OPS)},
                               "value": {"type": "number"}},
                "required": ["feature", "op", "value"],
                "additionalProperties": False,
            },
        },
        "facts_cited": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["thesis", "conditions", "facts_cited"],
    "additionalProperties": False,
}


def run(llm, features, facts, objections, **tags):
    """-> raw plan: thesis, conditions (list form), facts_cited."""
    prompt = json.dumps({"features": features, "facts": facts, "objections": objections})
    return llm("planner", SYSTEM, prompt, SCHEMA, **tags)


def build(raw, ticker, entry, facts, features):
    """Raw Planner output -> (plan, error). error is None when the plan is valid."""
    items = raw["conditions"]
    for c in items:
        if not (isinstance(c, dict) and c.get("feature") in FEATURE_NAMES and c.get("op") in OPS
                and isinstance(c.get("value"), (int, float)) and not isinstance(c.get("value"), bool)):
            return None, "each condition needs a known feature, an operator from %s, and a number" % list(OPS)
    if len({c["feature"] for c in items}) != len(items):
        return None, "one condition per feature"
    if not all(isinstance(k, str) for k in raw["facts_cited"]):
        return None, "facts_cited must be a list of fact keys"
    plan = {"ticker": ticker, "direction": "long", "entry": entry,
            "stop": entry * (1 - STOP), "target": entry * (1 + TARGET), "horizon_days": HORIZON,
            "thesis": raw["thesis"],
            "conditions": {c["feature"]: [c["op"], float(c["value"])] for c in items},
            "facts_cited": list(raw["facts_cited"])}
    return plan, validate_plan(plan, facts, features, entry)


def validate_plan(plan, facts, features, entry):
    """None if the plan is valid, else the reason it isn't."""
    if plan["direction"] != "long":
        return "direction must be long"
    if abs(plan["entry"] - entry) > TOLERANCE:
        return "entry must be the setup's close"
    if abs(plan["stop"] - entry * (1 - STOP)) > TOLERANCE or abs(plan["target"] - entry * (1 + TARGET)) > TOLERANCE:
        return "stop and target must be -3% and +5% of entry"
    if plan["horizon_days"] != HORIZON:
        return "horizon_days must be %d" % HORIZON
    if not plan["thesis"].strip():
        return "thesis is empty"
    if not MIN_CONDITIONS <= len(plan["conditions"]) <= MAX_CONDITIONS:
        return "need %d to %d conditions, got %d" % (MIN_CONDITIONS, MAX_CONDITIONS, len(plan["conditions"]))
    if not plan["facts_cited"]:
        return "facts_cited is empty"
    unknown = [k for k in plan["facts_cited"] if k not in facts]
    if unknown:
        return "facts_cited not in the Researcher's facts: %s" % ", ".join(unknown)
    for feature, (op, value) in plan["conditions"].items():
        if feature not in FEATURE_NAMES or op not in OPS:
            return "unknown feature or operator in conditions: %s %s" % (feature, op)
        if not OPS[op](features[feature], value):
            return "today's setup does not satisfy its own condition %s %s %s (today: %.4f)" % (
                feature, op, value, features[feature])
    return None
