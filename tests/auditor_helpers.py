"""Synthetic data and fake LLMs for the auditor tests. No network."""
import json
from types import SimpleNamespace

import numpy as np
import pandas as pd

from src.auditor.data import IV_END, IV_START, PRICE_END, PRICE_START


class FakeFetchers:
    """Deterministic random-walk prices, daily implied vol, quarterly earnings. Counts calls."""

    def __init__(self, seed=0, timeouts=0, timeout_if_longer_than=None):
        self.seed = seed
        self.calls = {"prices": 0, "dolthub": 0, "earnings": 0}
        self.timeouts = timeouts                       # first N dolthub calls time out
        self.timeout_if_longer_than = timeout_if_longer_than
        self.windows = []

    def prices(self, tickers, start, end):
        self.calls["prices"] += 1
        dates = pd.bdate_range(start, pd.Timestamp(end) - pd.Timedelta(days=1), name="Date")
        out = {}
        for k, t in enumerate(tickers):
            rng = np.random.default_rng(abs(hash((self.seed, t))) % 2**32)
            r = rng.normal(0.0003, 0.015, len(dates))
            close = 100 * np.exp(np.cumsum(r))
            open_ = close * np.exp(rng.normal(0, 0.004, len(dates)))
            high = np.maximum(close, open_) * (1 + np.abs(rng.normal(0, 0.006, len(dates))))
            low = np.minimum(close, open_) * (1 - np.abs(rng.normal(0, 0.006, len(dates))))
            out[t] = pd.DataFrame({"Open": open_, "High": high, "Low": low, "Close": close,
                                   "Adj Close": close * 0.99, "Volume": rng.integers(1e6, 2e6, len(dates)).astype(float)},
                                  index=dates)
        return out

    def dolthub(self, sql):
        self.calls["dolthub"] += 1
        a, b = sql.split("BETWEEN '")[1].split("' AND '")[0], sql.split("' AND '")[1].split("'")[0]
        self.windows.append((a, b))
        days = (pd.Timestamp(b) - pd.Timestamp(a)).days + 1
        if self.timeouts > 0:
            self.timeouts -= 1
            raise TimeoutError("fake timeout")
        if self.timeout_if_longer_than and days > self.timeout_if_longer_than:
            raise TimeoutError("fake timeout: window of %d days" % days)
        syms = [s.strip("'") for s in sql.split("IN (")[1].rstrip(")").split(",")]
        rows = []
        for d in pd.bdate_range(a, b):
            for s in syms:
                rows.append({"date": d.date().isoformat(), "act_symbol": s, "iv_current": "0.25", "hv_current": "0.22"})
        return rows

    def earnings(self, ticker):
        self.calls["earnings"] += 1
        return [d.date().isoformat() for d in pd.date_range("2014-01-25", "2026-09-30", freq="91D")]


def plan_reply(family="stock_long", group="energy", conditions=None, exit_=None, refuse=False, core=True):
    return {"refuse": {"is_refused": refuse, "reason": "illegal" if refuse else ""},
            "family": family, "universe_group": group,
            "conditions": conditions if conditions is not None else [{"feature": "ret_5d", "op": "<", "value": -0.02}],
            "exit": exit_ if exit_ is not None else ({"target_pct": 0.05, "stop_pct": 0.03, "horizon_days": 10}
                                                     if family == "stock_long" else {}),
            "hypothesis": "Dips revert.", "assumptions": ["'dip' read as ret_5d < -2%"], "not_tested": [],
            "core_trigger_tested": core}


def fake_llm(planner=None, naysayer_1=None, naysayer_2=None, reporter=None):
    """llm(role, system, prompt, schema, **tags). Each response: dict, callable(n), or exception."""
    responses = {"planner": planner or plan_reply(),
                 "naysayer_1": naysayer_1 or {"doubts": ["thin edge"], "followups": [{"id": "F2", "reason": "stability"}]},
                 "naysayer_2": naysayer_2 or {"critique": "Little evidence either way."},
                 "reporter": reporter or {"prose": "The idea was tested on history."}}
    calls = []

    def llm(role, system, prompt, schema, **tags):
        key = role if role != "naysayer" else tags.get("step")
        calls.append({"role": role, "step": tags.get("step"), "prompt": prompt})
        r = responses[key]
        n = sum(c["role"] == role and c["step"] == tags.get("step") for c in calls)
        r = r(n) if callable(r) else r
        if isinstance(r, Exception):
            raise r
        return r

    llm.calls = calls
    return llm


class FakeOpenAI:
    """OpenAI-style client returning queued JSON replies (strings) with token usage."""

    def __init__(self, replies):
        self.replies = list(replies)
        self.chat = SimpleNamespace(completions=self)
        self.n = 0

    def create(self, **kwargs):
        self.n += 1
        text = self.replies.pop(0) if self.replies else "{}"
        if not isinstance(text, str):
            text = json.dumps(text)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=text), finish_reason="stop")],
                               usage=SimpleNamespace(prompt_tokens=100, completion_tokens=50))


def make_panel_frame(closes, opens=None, highs=None, lows=None, start="2025-12-01", extra=None):
    """One ticker's panel frame from explicit prices (Adj Close = Close)."""
    n = len(closes)
    dates = pd.bdate_range(start, periods=n, name="Date")
    c = np.asarray(closes, float)
    f = pd.DataFrame({"Open": np.asarray(opens if opens is not None else c, float),
                      "High": np.asarray(highs if highs is not None else c, float),
                      "Low": np.asarray(lows if lows is not None else c, float),
                      "Close": c, "Adj Close": c}, index=dates)
    for k, v in (extra or {}).items():
        f[k] = v
    return f
