"""Prompts and reply schemas for the auditor's LLM roles: Planner, Naysayer (2 calls), Reporter.

The Planner sees the idea, the universe groups and the feature list, never dates or results.
The Naysayer sees plan v0 and the numbers; it picks follow-ups and writes doubts and a critique,
but cannot change the verdict. The Reporter adds explanation prose to a report whose verdict and
numbers code has already written; prose with a banned phrase is dropped.
"""
import json

from src.auditor.checks import FOLLOWUPS, MAX_FOLLOWUPS
from src.auditor.plan import FAMILIES, FEATURES, GROUPS, LLM_SCHEMA

DISCLAIMER = ("This is historical research on paper, not financial advice. Do not recommend trades, "
              "position sizes, or say anything will profit.")

PLANNER_SYSTEM = (
    "You are the Planner of a strategy-audit team. Translate a trading idea written in plain English "
    "into one AuditPlan for a historical backtest, or refuse it.\n"
    "Refuse (refuse.is_refused = true, with a reason) market manipulation (e.g. pump-and-dump, spoofing), "
    "trading on non-public information, and anything illegal.\n"
    "Otherwise map the idea onto exactly one family:\n"
    "- stock_long: buy the stock at the close when the conditions hold; exit at target_pct above entry, "
    "stop_pct below entry, or after horizon_days trading days (target and stop 0.01-0.20, horizon 1-20).\n"
    "- straddle_buy: buy a 10-trading-day at-the-money straddle (profits from big moves either way).\n"
    "- straddle_sell: sell that straddle (profits when the stock moves less than the premium).\n"
    "Choose one universe_group by name (never list tickers). Use 0 to 4 conditions, only on the listed "
    "features, each {feature, op, value} with op in > < >= <=. Implied-vol features (iv, hv, iv_hv_ratio, "
    "iv_minus_rv20) are for straddles only. For straddles set exit to {}.\n"
    "State every interpretation in assumptions (e.g. \"'uptrend' read as close above its 200-day average\"). "
    "List in not_tested every part of the idea you could not express (e.g. news sentiment). Set "
    "core_trigger_tested to false if the part of the idea that triggers a trade cannot be expressed with "
    "these features. Write hypothesis as one sentence. " + DISCLAIMER
)


def planner_prompt(idea, fix=None):
    body = {"idea": idea,
            "families": list(FAMILIES),
            "universe_groups": {g: t for g, t in GROUPS.items()},
            "features": {f: {"formula": formula, "families": list(fams)} for f, (formula, fams) in FEATURES.items()}}
    if fix:
        body["your_previous_plan_was_invalid"] = fix
    return json.dumps(body)


NAYSAYER_SYSTEM_1 = (
    "You are the Naysayer of a strategy-audit team. You see a frozen plan and its backtest results on a "
    "train period and a 6-month validation period, plus coded checks. State your doubts about whether the "
    "result is real (one sentence each), and choose up to %d follow-up robustness checks from this menu, "
    "each with a one-sentence reason:\n"
    "F1 earnings excluded: re-run without trades whose holding window contains an earnings date.\n"
    "F2 per-year stability: train mean per calendar year.\n"
    "F3 horizon sensitivity: horizons 5 and 20 days (stock_long only).\n"
    "F4 concentration: re-run without the ticker that contributes most to validation profit.\n"
    "Follow-ups can only downgrade a promising result; pick the ones that test your doubts. You cannot "
    "change the plan or the verdict. " % MAX_FOLLOWUPS + DISCLAIMER
)
NAYSAYER_SCHEMA_1 = {
    "type": "object",
    "properties": {"doubts": {"type": "array", "items": {"type": "string"}},
                   "followups": {"type": "array", "items": {
                       "type": "object", "properties": {"id": {"type": "string", "enum": list(FOLLOWUPS)},
                                                        "reason": {"type": "string"}},
                       "required": ["id", "reason"]}}},
    "required": ["doubts", "followups"],
}

NAYSAYER_SYSTEM_2 = (
    "You are the Naysayer of a strategy-audit team. You now see the follow-up results too. Write a final "
    "critique of at most 5 sentences: what the evidence does and does not show, and the biggest remaining "
    "risk. You cannot change the verdict. " + DISCLAIMER
)
NAYSAYER_SCHEMA_2 = {"type": "object", "properties": {"critique": {"type": "string"}}, "required": ["critique"]}

REPORTER_SYSTEM = (
    "You are the Reporter of a strategy-audit team. The verdict and every number are already written by "
    "code. Add 3 to 6 sentences of plain-English explanation for a hobby trader: what was tested, what the "
    "verdict means, and why. Do not change, add or round any number differently; refer to them loosely. "
    "Do not recommend anything. " + DISCLAIMER
)
REPORTER_SCHEMA = {"type": "object", "properties": {"prose": {"type": "string"}}, "required": ["prose"]}

BANNED = ("will profit", "guaranteed", "risk-free", "we recommend", "you should buy", "you should sell",
          "sure thing")


def prose_ok(text):
    low = (text or "").lower()
    return not any(b in low for b in BANNED)


def planner_schema():
    return LLM_SCHEMA
