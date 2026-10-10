"""Synthetic markets and fake Claude clients for the swarm tests. No network, no data files."""
import json
from types import SimpleNamespace

import pandas as pd

from src.features import FEATURE_NAMES
from src.tools import Market


def make_market(closes_by_ticker, setups, start="2025-01-01"):
    """closes_by_ticker: {ticker: [close, ...]}; High = Low = close unless edited after.
    setups: list of (ticker, row_index, split, label[, features dict])."""
    prices = {}
    for ticker, closes in closes_by_ticker.items():
        dates = pd.bdate_range(start, periods=len(closes), name="Date")
        prices[ticker] = pd.DataFrame({"Adj Close": closes, "High": closes, "Low": closes},
                                      index=dates, dtype=float)
    rows = []
    for s in setups:
        ticker, i, split, label = s[:4]
        feats = {k: 0.0 for k in FEATURE_NAMES}
        feats.update(s[4] if len(s) > 4 else {})
        rows.append({"ticker": ticker, "date": prices[ticker].index[i].date().isoformat(),
                     "split": split, "label": label, **feats})
    return Market(prices, pd.DataFrame(rows, columns=["ticker", "date", "split", "label"] + FEATURE_NAMES))


def set_bar(market, ticker, i, high=None, low=None):
    df = market.prices[ticker]
    if high is not None:
        df.iloc[i, df.columns.get_loc("High")] = high
    if low is not None:
        df.iloc[i, df.columns.get_loc("Low")] = low
    market.__post_init__()      # rebuild the numpy arrays


RESEARCHER_OUT = {"facts": [{"key": "ret_5d", "statement": "5-day return is 0."},
                            {"key": "vol_20d", "statement": "20-day volatility is 0."}]}
PLAN_OUT = {"thesis": "Momentum continues.",
            "conditions": [{"feature": "ret_5d", "op": ">=", "value": 0.0}],
            "facts_cited": ["ret_5d"]}


def fake_llm(planner=PLAN_OUT, naysayer=None, researcher=RESEARCHER_OUT):
    """An llm callable for agents. Each response is a dict or a function of the call number."""
    responses = {"researcher": researcher, "planner": planner,
                 "naysayer": naysayer or {"verdict": "approve", "objections": []}}
    calls = []

    def llm(agent, system, prompt, schema, **tags):
        calls.append({"agent": agent, "prompt": prompt, "tags": tags})
        r = responses[agent]
        n = sum(c["agent"] == agent for c in calls)
        return r(n) if callable(r) else r

    llm.calls = calls
    return llm


def _answers():
    return {"Researcher": RESEARCHER_OUT, "Planner": PLAN_OUT,
            "Naysayer": {"verdict": "approve", "objections": []}}


def _role(system, answers):
    return next(r for r in answers if "You are the %s" % r in system)


class FakeClient:
    """Stands in for anthropic.Anthropic(): answers by agent, read from the system prompt."""

    def __init__(self):
        self.answers = _answers()
        self.requests = []
        self.messages = SimpleNamespace(create=self._create)
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.requests.append(kwargs)
        text = json.dumps(self.answers[_role(kwargs["system"], self.answers)])
        return SimpleNamespace(
            stop_reason="end_turn",
            usage=SimpleNamespace(input_tokens=1000, output_tokens=100),
            content=[SimpleNamespace(type="text", text=text)])


class FakeDeepSeekClient:
    """Stands in for OpenAI(base_url=DeepSeek). `queued` maps a role to replies sent before the default."""

    def __init__(self, queued=None, finish_reason="stop"):
        self.answers = _answers()
        self.queued = {k: list(v) for k, v in (queued or {}).items()}
        self.finish_reason = finish_reason
        self.requests = []
        self.suppressed = []    # was neatlogs auto-patching suppressed during each call?
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        from neatlogs.core import is_patching_suppressed
        self.requests.append(kwargs)
        self.suppressed.append(is_patching_suppressed())
        role = _role(kwargs["messages"][0]["content"], self.answers)
        queue = self.queued.get(role)
        text = queue.pop(0) if queue else json.dumps(self.answers[role])
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=text), finish_reason=self.finish_reason)],
            usage=SimpleNamespace(prompt_tokens=1000, completion_tokens=100))


class FakeTracker:
    """Records neatlogs spans the way neatlogs.core.LLMTracker would receive them."""

    def __init__(self):
        self.started = 0
        self.ended = []

    def start_llm_span(self, model=None, provider=None, framework=None, node_type="llm_call", node_name=None):
        from neatlogs.core import current_span_id_context
        self.started += 1
        return SimpleNamespace(span_id="s%d" % self.started, parent_span_id=current_span_id_context.get(),
                               tags=["trading-swarm"], node_type=node_type, node_name=node_name, model=model)

    def end_llm_span(self, span, success=True, error=None):
        span.success = success
        self.ended.append(span)
