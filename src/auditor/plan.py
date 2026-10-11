"""AuditPlan: the Planner's JSON, validated, frozen and hashed (spec sections 2, 5, 6).

The LLM replies with conditions in list form [{feature, op, value}]; code converts them to the
map form {feature: [op, value]}. Plan v0 is the validated map form as canonical JSON (sorted
keys), and its hash is the SHA-256 of that text. Code, not the LLM, writes the "What was
tested" line.
"""
import hashlib
import json

FAMILIES = ("stock_long", "straddle_buy", "straddle_sell")
STRADDLES = ("straddle_buy", "straddle_sell")
OPS = (">", "<", ">=", "<=")
MAX_CONDITIONS = 4

# Fixed from the 50 tickers of the 50-stock spike, as of 2025-12-31 (survivorship bias stated in every report).
GROUPS = {
    "all_50": ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "BRK-B", "JPM", "V",
               "JNJ", "UNH", "XOM", "PG", "MA", "HD", "CVX", "MRK", "ABBV", "PEP",
               "KO", "AVGO", "COST", "LLY", "WMT", "BAC", "PFE", "TMO", "CSCO", "MCD",
               "ABT", "CRM", "DIS", "ACN", "ADBE", "NFLX", "WFC", "TXN", "NKE", "AMD",
               "INTC", "QCOM", "HON", "UNP", "IBM", "CAT", "GS", "BA", "AMGN", "SBUX"],
    "tech": ["AAPL", "MSFT", "NVDA", "AVGO", "CSCO", "CRM", "ACN", "ADBE", "TXN", "AMD", "INTC",
             "QCOM", "IBM", "GOOGL", "META", "NFLX", "DIS"],
    "financials": ["BRK-B", "JPM", "V", "MA", "BAC", "WFC", "GS"],
    "healthcare": ["JNJ", "UNH", "MRK", "ABBV", "LLY", "PFE", "TMO", "ABT", "AMGN"],
    "energy": ["XOM", "CVX"],
    "consumer": ["AMZN", "TSLA", "HD", "MCD", "NKE", "SBUX", "PG", "KO", "PEP", "COST", "WMT"],
    "industrials": ["HON", "UNP", "CAT", "BA"],
    "mega_cap": ["AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META", "AVGO", "TSLA", "BRK-B", "LLY"],
}
SECTOR_GROUPS = ("tech", "financials", "healthcare", "energy", "consumer", "industrials")
THIN_GROUPS = ("energy", "industrials")   # too few tickers to reach validation n >= 30 usually

# feature -> (formula, families allowed). Formulas match src/features.py and scripts/spikes/.
ALL = FAMILIES
FEATURES = {
    "ret_1d": ("Adj Close today / Adj Close 1 trading day ago - 1", ALL),
    "ret_5d": ("Adj Close today / Adj Close 5 trading days ago - 1", ALL),
    "ret_10d": ("Adj Close today / Adj Close 10 trading days ago - 1", ALL),
    "ret_20d": ("Adj Close today / Adj Close 20 trading days ago - 1", ALL),
    "vol_20d": ("standard deviation of the last 20 daily returns", ALL),
    "close_to_ma50": ("Adj Close / mean Adj Close of the last 50 days (today included)", ALL),
    "close_to_ma200": ("Adj Close / mean Adj Close of the last 200 days (today included)", ALL),
    "spy_ret_5d": ("SPY close today / SPY close 5 trading days ago - 1", ALL),
    "spy_ret_20d": ("SPY close today / SPY close 20 trading days ago - 1", ALL),
    "spy_close_to_ma50": ("SPY close / its 50-day mean", ALL),
    "vix_level": ("^VIX close", ALL),
    "vix_chg_5d": ("^VIX today / ^VIX 5 trading days ago - 1", ALL),
    "rel_ret_20d": ("ret_20d - spy_ret_20d", ALL),
    "vol_ratio_5d": ("today's volume / mean volume of the previous 5 days", ALL),
    "vol_ratio_20d": ("today's volume / mean volume of the previous 20 days", ALL),
    "iv": ("implied volatility (annualized), latest DoltHub iv_current", STRADDLES),
    "hv": ("historical volatility (annualized), latest DoltHub hv_current", STRADDLES),
    "iv_hv_ratio": ("iv / hv", STRADDLES),
    "iv_minus_rv20": ("iv - vol_20d x sqrt(252)", STRADDLES),
    "earnings_within_10d": ("1 if a report date falls in the next 10 trading days, else 0", ALL),
    "days_since_earnings": ("trading days since the last report date", ALL),
}
IV_FEATURES = ("iv", "hv", "iv_hv_ratio", "iv_minus_rv20")
EARNINGS_FEATURES = ("earnings_within_10d", "days_since_earnings")

PLAN_KEYS = ("refuse", "family", "universe_group", "conditions", "exit", "hypothesis",
             "assumptions", "not_tested", "core_trigger_tested")

# The LLM's reply schema. Top-level keys and types are checked by src/llm.py schema_error;
# nested fields are checked by validate() here.
LLM_SCHEMA = {
    "type": "object",
    "properties": {
        "refuse": {"type": "object", "properties": {"is_refused": {"type": "boolean"},
                                                    "reason": {"type": "string"}},
                   "required": ["is_refused", "reason"]},
        "family": {"type": "string", "enum": list(FAMILIES)},
        "universe_group": {"type": "string", "enum": list(GROUPS)},
        "conditions": {"type": "array", "items": {
            "type": "object",
            "properties": {"feature": {"type": "string", "enum": list(FEATURES)},
                           "op": {"type": "string", "enum": list(OPS)},
                           "value": {"type": "number"}},
            "required": ["feature", "op", "value"]}},
        "exit": {"type": "object", "properties": {"target_pct": {"type": "number"},
                                                  "stop_pct": {"type": "number"},
                                                  "horizon_days": {"type": "integer"}}},
        "hypothesis": {"type": "string"},
        "assumptions": {"type": "array", "items": {"type": "string"}},
        "not_tested": {"type": "array", "items": {"type": "string"}},
        "core_trigger_tested": {"type": "boolean"},
    },
    "required": list(PLAN_KEYS),
}


def _is_number(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def to_map(raw):
    """LLM reply -> plan with map-form conditions. Raises ValueError on a malformed condition list."""
    conds = raw.get("conditions")
    if isinstance(conds, dict):
        items = [{"feature": f, "op": v[0], "value": v[1]} for f, v in conds.items()
                 if isinstance(v, (list, tuple)) and len(v) == 2]
        if len(items) != len(conds):
            raise ValueError("each condition needs an operator and a value")
    elif isinstance(conds, list):
        items = conds
    else:
        raise ValueError("conditions must be a list of {feature, op, value}")
    out = {}
    for c in items:
        if not isinstance(c, dict) or set(c) - {"feature", "op", "value"} or len(c) != 3:
            raise ValueError("each condition needs exactly feature, op and value")
        if c["feature"] in out:
            raise ValueError("one condition per feature (%s repeated)" % c["feature"])
        out[c["feature"]] = [c["op"], c["value"]]
    plan = {k: raw.get(k) for k in PLAN_KEYS}
    plan["conditions"] = out
    ex = plan.get("exit")
    if isinstance(ex, dict) and isinstance(ex.get("horizon_days"), float) and ex["horizon_days"].is_integer():
        plan["exit"] = dict(ex, horizon_days=int(ex["horizon_days"]))     # JSON numbers like 10.0
    return plan


def validate(plan):
    """None if the map-form plan is valid, else the reason. A refused plan is valid as a refusal."""
    refuse = plan.get("refuse")
    if not isinstance(refuse, dict) or not isinstance(refuse.get("is_refused"), bool):
        return "refuse must be {is_refused: bool, reason: str}"
    if refuse["is_refused"]:
        if not isinstance(refuse.get("reason"), str) or not refuse["reason"].strip():
            return "a refusal needs a reason"
        return None
    family = plan.get("family")
    if family not in FAMILIES:
        return "family must be one of %s" % ", ".join(FAMILIES)
    group = plan.get("universe_group")
    if not isinstance(group, str) or group not in GROUPS:
        return "universe_group must be one of %s (a group name, not a ticker list)" % ", ".join(GROUPS)
    conds = plan.get("conditions")
    if not isinstance(conds, dict) or len(conds) > MAX_CONDITIONS:
        return "0 to %d conditions allowed" % MAX_CONDITIONS
    for feature, cond in conds.items():
        if feature not in FEATURES:
            return "unknown feature %r" % feature
        if family not in FEATURES[feature][1]:
            return "feature %s is not available for %s (implied-vol features are straddles only)" % (feature, family)
        op, value = cond
        if op not in OPS:
            return "operator must be one of %s, got %r" % (" ".join(OPS), op)
        if not _is_number(value):
            return "condition value for %s must be a number" % feature
    if family == "stock_long":
        ex = plan.get("exit")
        if not isinstance(ex, dict):
            return "stock_long needs exit {target_pct, stop_pct, horizon_days}"
        for key in ("target_pct", "stop_pct"):
            if not _is_number(ex.get(key)) or not 0.01 <= ex[key] <= 0.20:
                return "exit.%s must be between 0.01 and 0.20" % key
        h = ex.get("horizon_days")
        if not isinstance(h, int) or isinstance(h, bool) or not 1 <= h <= 20:
            return "exit.horizon_days must be an integer from 1 to 20"
    if not isinstance(plan.get("hypothesis"), str) or not plan["hypothesis"].strip():
        return "hypothesis must be a non-empty sentence"
    for key in ("assumptions", "not_tested"):
        if not isinstance(plan.get(key), list) or not all(isinstance(s, str) for s in plan[key]):
            return "%s must be a list of strings" % key
    if not isinstance(plan.get("core_trigger_tested"), bool):
        return "core_trigger_tested must be true or false"
    return None


def normalize(plan):
    """The stored v0: map-form conditions with float values; exit only for stock_long."""
    out = dict(plan)
    if plan["refuse"]["is_refused"]:
        return out
    out["conditions"] = {f: [op, float(v)] for f, (op, v) in sorted(plan["conditions"].items())}
    if plan["family"] == "stock_long":
        ex = plan["exit"]
        out["exit"] = {"target_pct": float(ex["target_pct"]), "stop_pct": float(ex["stop_pct"]),
                       "horizon_days": int(ex["horizon_days"])}
    else:
        out["exit"] = None
    return out


def canonical(plan):
    return json.dumps(plan, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def plan_hash(plan):
    return hashlib.sha256(canonical(plan).encode("utf-8")).hexdigest()


def _fmt(value):
    return ("%g" % value) if _is_number(value) else str(value)


def what_was_tested(plan):
    """One line, written by code from the plan JSON."""
    group = plan["universe_group"]
    conds = " and ".join("%s %s %s" % (f, op, _fmt(v)) for f, (op, v) in sorted(plan["conditions"].items()))
    entry = ("enter when " + conds) if conds else "enter on every trading day (no conditions)"
    if plan["family"] == "stock_long":
        ex = plan["exit"]
        exit_ = "exit at +%g%% / -%g%% / %d days" % (100 * ex["target_pct"], 100 * ex["stop_pct"], ex["horizon_days"])
    else:
        exit_ = "hold the at-the-money straddle 10 trading days"
    not_tested = "; ".join(plan["not_tested"]) if plan["not_tested"] else "nothing"
    return "%s on %s (%d tickers): %s; %s. Not tested: %s." % (
        plan["family"], group, len(GROUPS[group]), entry, exit_, not_tested)


def uses_earnings(plan):
    return any(f in EARNINGS_FEATURES for f in plan.get("conditions") or {})
