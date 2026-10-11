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


# ----------------------------------------------------------------------------- client-level fakes and faults

class FakeAuditorClient:
    """Stands in for OpenAI(base_url=DeepSeek) for the auditor's roles, so src.llm.make_llm's retry path is
    exercised for real. `queued` maps a role (planner/naysayer/reporter) to reply texts sent before the default."""

    def __init__(self, queued=None):
        from types import SimpleNamespace
        self.queued = {k: list(v) for k, v in (queued or {}).items()}
        self.requests = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    @staticmethod
    def _role(system):
        for role in ("planner", "naysayer", "reporter"):
            if "You are the %s" % role.capitalize() in system:
                return role
        raise ValueError("unknown role in system prompt")

    def _create(self, **kwargs):
        from types import SimpleNamespace
        self.requests.append(kwargs)
        system, user = kwargs["messages"][0]["content"], kwargs["messages"][1]["content"]
        role = self._role(system)
        queue = self.queued.get(role)
        if queue:
            text = queue.pop(0)
        elif role == "planner":
            text = json.dumps(plan_from_idea(json.loads(user).get("idea", "")))
        elif role == "naysayer":
            text = json.dumps({"critique": "%s: see the coded checks." % FAKE_PREFIX, "doubts": ["%s: one window" % FAKE_PREFIX]})
        else:
            text = json.dumps({"prose": "%s: template explanation." % FAKE_PREFIX})
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=text), finish_reason="stop")],
                               usage=SimpleNamespace(prompt_tokens=TOKENS_IN, completion_tokens=TOKENS_OUT))


class EmptyFirstReply:
    """Wraps a real OpenAI-style client so the first reply's content is empty (`--fault llm_empty`, section 6).
    The wrapper's own retry in src.llm then recovers; the audit labels that recovery INJECTED."""

    def __init__(self, client):
        from types import SimpleNamespace
        self._client, self._fired = client, False
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        resp = self._client.chat.completions.create(**kwargs)
        if not self._fired:
            self._fired = True
            resp.choices[0].message.content = ""
        return resp
