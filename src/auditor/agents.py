"""The auditor's LLM agents (AUDITOR_SPEC section 4): Planner, Naysayer, Reporter. Prompts and reply
schemas live here; every call goes through the llm(agent, system, prompt, schema, **tags) wrapper."""
import json
import re

from .plan import EXIT_RANGES, FEATURES, MAX_CONDITIONS, SCHEMA as PLAN_SCHEMA
from .universe import GROUPS

FEATURE_FORMULAS = {
    "ret_1d/ret_5d/ret_10d/ret_20d": "adjusted close today / adjusted close N trading days ago - 1",
    "vol_20d": "standard deviation of the last 20 daily returns",
    "close_to_ma50/close_to_ma200": "adjusted close today / mean adjusted close of the last 50 or 200 days",
    "spy_ret_5d/spy_ret_20d": "SPY close today / SPY close N trading days ago - 1",
    "spy_close_to_ma50": "SPY close / its 50-day mean",
    "vix_level": "VIX close", "vix_chg_5d": "VIX today / VIX 5 trading days ago - 1",
    "rel_ret_20d": "ret_20d - spy_ret_20d",
    "vol_ratio_5d/vol_ratio_20d": "today's volume / mean volume of the previous 5 or 20 days",
    "iv": "implied volatility (straddles only)", "hv": "historical volatility (straddles only)",
    "iv_hv_ratio": "iv / hv (straddles only)", "iv_minus_rv20": "iv - vol_20d x sqrt(252) (straddles only)",
    "earnings_within_10d": "1 if an earnings report falls in the next 10 trading days, else 0",
    "days_since_earnings": "trading days since the last earnings report",
}

PLANNER_SYSTEM = (
    "You are the Planner of the Strategy Auditor, a paper-trading research tool that tests trading ideas on "
    "historical data and returns a verdict. This is research, not financial advice. Translate the user's idea into "
    "one AuditPlan, or refuse it.\n\n"
    "Refuse (refuse.is_refused = true, with the reason) any idea that involves market manipulation, trading on "
    "non-public information, or anything illegal. When refusing, the other fields may be empty.\n\n"
    "Families (field family, pick exactly one):\n"
    "- stock_long: buy at the close on days that satisfy the conditions; exit at a target gain, a stop loss, or after a "
    "horizon in trading days (exit.target_pct and stop_pct between %s and %s as fractions, horizon_days between %d and %d).\n"
    "- straddle_buy: buy an at-the-money straddle at the close on days that satisfy the conditions; hold 10 days.\n"
    "- straddle_sell: sell the same straddle; hold 10 days. Exit is ignored for straddles.\n\n"
    "Universe groups (field universe_group: pick exactly one name, never list tickers): %s.\n\n"
    "Conditions (field conditions): 0 to %d conditions, each {feature, op, value} with op in >, <, >=, <= and a numeric value, one per "
    "feature. Features and formulas: %s. Implied-vol features are only allowed for straddles. You never see dates; "
    "the backtest decides the windows.\n\n"
    "State every reading you made in assumptions (for example \"'uptrend' read as close above its 200-day average\"). "
    "List in not_tested every part of the idea that cannot be expressed with these families and features (for example "
    "news sentiment, intraday data, short selling, crypto). If the part of the idea that triggers a trade cannot be "
    "expressed, set core_trigger_tested to false. Keep hypothesis to one sentence. Reply only with the JSON object."
) % (EXIT_RANGES["target_pct"][0], EXIT_RANGES["target_pct"][1], EXIT_RANGES["horizon_days"][0],
     EXIT_RANGES["horizon_days"][1],
     "; ".join("%s = %s" % (g, ", ".join(t)) for g, t in GROUPS.items()), MAX_CONDITIONS,
     "; ".join("%s: %s" % kv for kv in FEATURE_FORMULAS.items()))

NAYSAYER_SYSTEM = (
    "You are the Naysayer of the Strategy Auditor, a paper-trading research tool. Coded checks and verdict rules have "
    "already run; you cannot change the verdict or any number. Your job is to state, in plain language, the doubts a "
    "careful reader should have about this backtest: thin evidence, decay from train to validation, a result the "
    "no-condition baseline explains, cost realism, tail risk, data drops, and anything that looks like curve fitting. "
    "You are given summary statistics only: no tickers and no dates. Do not use outside knowledge of markets or "
    "specific stocks. No financial advice, no position sizing. Reply with a short critique (3 to 6 sentences) and a "
    "list of specific doubts."
)
NAYSAYER_SCHEMA = {"type": "object", "properties": {"critique": {"type": "string"},
                                                    "doubts": {"type": "array", "items": {"type": "string"}}},
                   "required": ["critique", "doubts"]}

REPORTER_SYSTEM = (
    "You are the Reporter of the Strategy Auditor. You are given the finished report, written by code. Add 2 to 5 "
    "sentences of plain-language explanation of what was tested and what the numbers mean for a hobby trader. You "
    "must not change or restate any number differently, must not change the verdict, must not recommend buying or "
    "selling, must not give position sizes, and must not use the phrases 'will profit', 'guaranteed', 'risk-free', "
    "'we recommend', 'you should buy', 'you should sell' or 'sure thing'. This is not financial advice."
)
REPORTER_SCHEMA = {"type": "object", "properties": {"prose": {"type": "string"}}, "required": ["prose"]}

_DATE = re.compile(r"\b(?:19|20)\d\d(?:-\d\d(?:-\d\d)?)?\b")


def run_planner(llm, idea, fix_reason):
    """-> raw Planner reply. fix_reason is the validator's message after an invalid plan (one fix allowed)."""
    body = {"idea": idea}
    if fix_reason:
        body["previous_plan_was_invalid"] = fix_reason
        body["instruction"] = "Return a corrected plan that fixes this problem."
    return llm("planner", PLANNER_SYSTEM, json.dumps(body), PLAN_SCHEMA, step="plan")


def naysayer_context(results):
    """What the Naysayer sees: summary statistics only, with dates masked and no tickers."""
    ctx = {"what_tested": results.get("what_tested"),
           "base": results.get("base"), "baseline": results.get("baseline"),
           "stricter": results.get("stricter"), "tail": results.get("tail"),
           "checks": [{"check": c["check"], "passed": c["passed"], "note": c["note"]} for c in results.get("checks") or []],
           "drops": results.get("drops")}
    return _mask(ctx)


def _mask(value):
    """Replace dates/years inside string values only; numbers and structure are untouched."""
    if isinstance(value, str):
        return _DATE.sub("[date]", value)
    if isinstance(value, dict):
        return {k: _mask(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_mask(v) for v in value]
    if hasattr(value, "item"):
        return value.item()
    return value


def run_naysayer(llm, context):
    """-> {"critique", "doubts"} (the only Naysayer LLM call in M1: the final critique)."""
    out = llm("naysayer", NAYSAYER_SYSTEM, json.dumps(context), NAYSAYER_SCHEMA, step="critique")
    return {"critique": str(out.get("critique", "")), "doubts": [str(d) for d in out.get("doubts", []) or []]}


def run_reporter(llm, report_md):
    """-> prose string (the reserved 8th call)."""
    out = llm("reporter", REPORTER_SYSTEM, report_md, REPORTER_SCHEMA, step="report")
    return str(out.get("prose", ""))
