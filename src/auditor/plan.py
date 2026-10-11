"""AuditPlan (AUDITOR_SPEC section 5): the Planner's reply schema, validation to the map form, the frozen
plan's canonical JSON and SHA-256 hash, and the code-written "What was tested" line."""
import hashlib
import json

from src.tools import OPS

from .universe import GROUPS

FAMILIES = ("stock_long", "straddle_buy", "straddle_sell")
STRADDLE_FAMILIES = ("straddle_buy", "straddle_sell")

# Feature -> which families may use it (section 6 table).
FEATURES = {
    "ret_1d": "all", "ret_5d": "all", "ret_10d": "all", "ret_20d": "all", "vol_20d": "all",
    "close_to_ma50": "all", "close_to_ma200": "all",
    "spy_ret_5d": "all", "spy_ret_20d": "all", "spy_close_to_ma50": "all", "vix_level": "all", "vix_chg_5d": "all",
    "rel_ret_20d": "all", "vol_ratio_5d": "all", "vol_ratio_20d": "all",
    "iv": "straddle", "hv": "straddle", "iv_hv_ratio": "straddle", "iv_minus_rv20": "straddle",
    "earnings_within_10d": "all", "days_since_earnings": "all",
}
MAX_CONDITIONS = 4
EXIT_RANGES = {"target_pct": (0.01, 0.20), "stop_pct": (0.01, 0.20), "horizon_days": (1, 20)}
HOLD_DAYS = 10

SCHEMA = {
    "type": "object",
    "properties": {
        "refuse": {"type": "object", "properties": {"is_refused": {"type": "boolean"}, "reason": {"type": "string"}},
                   "required": ["is_refused", "reason"]},
        "family": {"type": "string", "enum": list(FAMILIES)},
        "universe_group": {"type": "string", "enum": list(GROUPS)},
        "conditions": {"type": "array", "items": {"type": "object", "properties": {
            "feature": {"type": "string", "enum": list(FEATURES)}, "op": {"type": "string", "enum": list(OPS)},
            "value": {"type": "number"}}, "required": ["feature", "op", "value"]}},
        "exit": {"type": "object", "properties": {"target_pct": {"type": "number"}, "stop_pct": {"type": "number"},
                                                  "horizon_days": {"type": "integer"}}},
        "hypothesis": {"type": "string"},
        "assumptions": {"type": "array", "items": {"type": "string"}},
        "not_tested": {"type": "array", "items": {"type": "string"}},
        "core_trigger_tested": {"type": "boolean"},
    },
    "required": ["refuse", "family", "universe_group", "conditions", "hypothesis", "assumptions",
                 "not_tested", "core_trigger_tested"],
}


def _number(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def validate(raw):
    """Raw Planner reply -> (map-form plan, None) or (None, reason). A refusal is a valid plan with refused=True."""
    if not isinstance(raw, dict):
        return None, "plan is not an object"
    refuse = raw.get("refuse")
    if isinstance(refuse, dict) and refuse.get("is_refused") is True:
        return {"refused": True, "reason": str(refuse.get("reason", ""))}, None
    family = raw.get("family")
    if family not in FAMILIES:
        return None, "unknown family %r; use one of %s" % (family, list(FAMILIES))
    group = raw.get("universe_group")
    if not isinstance(group, str) or group not in GROUPS:
        return None, "universe_group must be one of %s, not a ticker list or %r" % (list(GROUPS), group)
    items = raw.get("conditions")
    if not isinstance(items, list):
        return None, "conditions must be a list"
    if len(items) > MAX_CONDITIONS:
        return None, "at most %d conditions, got %d" % (MAX_CONDITIONS, len(items))
    conditions = {}
    for c in items:
        if not isinstance(c, dict):
            return None, "each condition is an object {feature, op, value}"
        feature, op, value = c.get("feature"), c.get("op"), c.get("value")
        if feature not in FEATURES:
            return None, "unknown feature %r; use one of %s" % (feature, list(FEATURES))
        if op not in OPS:
            return None, "unknown operator %r; use one of %s" % (op, list(OPS))
        if not _number(value):
            return None, "condition value for %s must be numeric, got %r" % (feature, value)
        if feature in conditions:
            return None, "one condition per feature (%s given twice)" % feature
        if FEATURES[feature] == "straddle" and family == "stock_long":
            return None, "implied-vol feature %s is not allowed for stock_long" % feature
        conditions[feature] = [op, value if isinstance(value, int) else float(value)]
    plan = {"refused": False, "family": family, "universe_group": group, "conditions": conditions}
    if family == "stock_long":
        exit_ = raw.get("exit")
        if not isinstance(exit_, dict):
            return None, "exit {target_pct, stop_pct, horizon_days} is required for stock_long"
        clean = {}
        for key, (lo, hi) in EXIT_RANGES.items():
            v = exit_.get(key)
            if not _number(v) or not lo <= v <= hi:
                return None, "exit %s must be between %s and %s, got %r" % (key, lo, hi, v)
            clean[key] = int(v) if key == "horizon_days" else float(v)
        plan["exit"] = clean
    not_tested = raw.get("not_tested")
    if not isinstance(not_tested, list) or not all(isinstance(x, str) for x in not_tested):
        return None, "not_tested must be a list of strings"
    if not isinstance(raw.get("core_trigger_tested"), bool):
        return None, "core_trigger_tested must be a boolean"
    assumptions = raw.get("assumptions", [])
    plan.update({"hypothesis": str(raw.get("hypothesis", "")),
                 "assumptions": [str(a) for a in assumptions] if isinstance(assumptions, list) else [],
                 "not_tested": list(not_tested), "core_trigger_tested": raw["core_trigger_tested"]})
    return plan, None


def canonical(plan):
    return json.dumps(plan, sort_keys=True, separators=(",", ":"))


def plan_hash(plan):
    return hashlib.sha256(canonical(plan).encode("utf-8")).hexdigest()


def what_tested(plan):
    """Code-written summary line, e.g. 'stock_long on all_50 (50 tickers): enter when ret_5d < -0.03 and
    close_to_ma200 > 1.0; exit at +5% / -3% / 10 days. Not tested: nothing.'"""
    if plan.get("refused"):
        return "Refused: %s" % plan.get("reason", "")
    group = plan["universe_group"]
    conds = plan["conditions"]
    entry = ("enter when " + " and ".join("%s %s %s" % (f, op, _fmt_value(v)) for f, (op, v) in conds.items())
             if conds else "enter every day")
    if plan["family"] == "stock_long":
        e = plan["exit"]
        exit_ = "exit at +%s%% / -%s%% / %d days" % (_fmt(100 * e["target_pct"]), _fmt(100 * e["stop_pct"]), e["horizon_days"])
    else:
        exit_ = "hold %d days" % HOLD_DAYS
    not_tested = "; ".join(plan.get("not_tested") or []) or "nothing"
    return "%s on %s (%d tickers): %s; %s. Not tested: %s." % (plan["family"], group, len(GROUPS[group]), entry, exit_, not_tested)


def _fmt(v):
    """Percent figures: 5.000000000000001 -> '5'."""
    return "%g" % v


def _fmt_value(v):
    """Condition values: ints as given (1), floats keep a decimal point (1.0, -0.03)."""
    if isinstance(v, int):
        return str(v)
    s = "%g" % v
    return s if ("." in s or "e" in s) else s + ".0"
