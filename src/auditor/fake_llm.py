"""A fake LLM for tests and development runs (AUDITOR_SPEC section 8: no real calls without a key).

The Planner reply comes from keyword rules on the idea text; every reply is prefixed FAKE LLM so a report or
screen built from it can never pass as a model's work. Spans are recorded like real calls.
"""
import json

from src.llm import PRICES

FAKE_PREFIX = "FAKE LLM"
FAKE_MODEL = "fake"
TOKENS_IN, TOKENS_OUT = 1000, 100

REFUSE_WORDS = ("manipulat", "insider", "pump", "non-public", "front-run", "spoof")
UNTESTABLE_WORDS = ("news", "sentiment", "tweet", "twitter", "reddit", "headline")
GROUP_WORDS = [("tech", "tech"), ("mega", "mega_cap"), ("financ", "financials"), ("bank", "financials"),
               ("health", "healthcare"), ("pharma", "healthcare"), ("energy", "energy"), ("oil", "energy"),
               ("consumer", "consumer"), ("retail", "consumer"), ("industrial", "industrials")]
CONDITION_WORDS = [
    ("earnings", "earnings_within_10d", ">=", 1, "'before earnings' read as an earnings report within the next 10 trading days"),
    ("low-vol", "vol_20d", "<", 0.012, "'low volatility' read as a 20-day daily volatility below 1.2%"),
    ("low volatility", "vol_20d", "<", 0.012, "'low volatility' read as a 20-day daily volatility below 1.2%"),
    ("low vol", "vol_20d", "<", 0.012, "'low volatility' read as a 20-day daily volatility below 1.2%"),
    ("dip", "ret_5d", "<", -0.03, "'dip' read as a 5-day return below -3%"),
    ("uptrend", "close_to_ma200", ">", 1.0, "'uptrend' read as close above its 200-day average"),
    ("momentum", "ret_20d", ">", 0.05, "'momentum' read as a 20-day return above +5%"),
    ("breakout", "ret_20d", ">", 0.05, "'breakout' read as a 20-day return above +5%"),
    ("oversold", "ret_10d", "<", -0.05, "'oversold' read as a 10-day return below -5%"),
]


def plan_from_idea(idea):
    low = idea.lower()
    base = {"refuse": {"is_refused": False, "reason": ""}, "family": "stock_long", "universe_group": "all_50",
            "conditions": [], "exit": {"target_pct": 0.05, "stop_pct": 0.03, "horizon_days": 10},
            "hypothesis": "%s: %s" % (FAKE_PREFIX, idea), "assumptions": [], "not_tested": [], "core_trigger_tested": True}
    if any(w in low for w in REFUSE_WORDS):
        base["refuse"] = {"is_refused": True, "reason": "%s: market manipulation or non-public information" % FAKE_PREFIX}
        return base
    if "straddle" in low:
        base["family"] = "straddle_sell" if "sell" in low else "straddle_buy"
    for word, group in GROUP_WORDS:
        if word in low:
            base["universe_group"] = group
            break
    seen = set()
    for word, feature, op, value, reading in CONDITION_WORDS:
        if word in low and feature not in seen:
            seen.add(feature)
            base["conditions"].append({"feature": feature, "op": op, "value": value})
            base["assumptions"].append(reading)
    if any(w in low for w in UNTESTABLE_WORDS):
        base["core_trigger_tested"] = False
        base["not_tested"] = ["news sentiment"]
        base["assumptions"].append("the trigger (news or sentiment) cannot be expressed with the available features")
    if not base["assumptions"]:
        base["assumptions"].append("%s: no keyword matched; enter every day of the group" % FAKE_PREFIX)
    return base


def make_fake_llm(tracer):
    """Same signature as src.llm.make_llm's result: llm(agent, system, prompt, schema, **tags)."""
    price_in, price_out = PRICES["deepseek-flash"]

    def llm(agent, system, prompt, schema, **tags):
        with tracer.span("llm", agent, model=FAKE_MODEL, **tags) as rec:
            rec["input"] = prompt
            rec["prompt_tokens"], rec["completion_tokens"] = TOKENS_IN, TOKENS_OUT
            rec["cost"] = (TOKENS_IN * price_in + TOKENS_OUT * price_out) / 1e6
            rec["attempts"] = 1
            if agent == "planner":
                body = json.loads(prompt)
                out = plan_from_idea(body.get("idea", ""))
            elif agent == "naysayer":
                ctx = json.loads(prompt) if prompt.startswith("{") else {}
                val = ((ctx.get("base") or {}).get("validation") or {})
                out = {"critique": "%s: the validation mean is %s over %s trades; read the coded checks, not this sentence."
                                   % (FAKE_PREFIX, val.get("mean", "n/a"), val.get("n", "n/a")),
                       "doubts": ["%s: one validation window" % FAKE_PREFIX, "%s: costs are approximated" % FAKE_PREFIX]}
            elif agent == "reporter":
                out = {"prose": "%s: template explanation. The verdict rests on the numbers above." % FAKE_PREFIX}
            else:
                raise ValueError("fake llm has no role %r" % agent)
            rec["output"] = json.dumps(out)
            return out

    return llm
