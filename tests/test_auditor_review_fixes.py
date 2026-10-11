"""Regression tests for the issues found in the independent review of the auditor."""
import io
import json
import math
import os

import numpy as np
import pandas as pd
import pytest

from src.auditor import backtest, data
from src.auditor.audit import Audit, _jsonable
from src.auditor.data import Fetchers, Panel, fetch_iv_window, iv_features, load_earnings, load_iv, report_dates
from src.tracing import Tracer
from tests.auditor_helpers import FakeFetchers, fake_llm, make_panel_frame, plan_reply


def test_iv_features_join_dates_with_different_units():
    dates = pd.DatetimeIndex(pd.bdate_range("2026-01-05", periods=5)).as_unit("s")       # yfinance, pandas 3
    rows = pd.DataFrame({"date": pd.to_datetime(["2026-01-05"]).as_unit("us"), "iv_current": [0.3], "hv_current": [0.2]})
    f = iv_features(dates, rows, np.zeros(5))
    assert f["iv"].iloc[0] == 0.3


def test_earnings_failure_is_not_cached_as_no_coverage(tmp_path):
    class Flaky(FakeFetchers):
        def earnings(self, ticker):
            self.calls["earnings"] += 1
            if self.calls["earnings"] == 1:
                raise RuntimeError("rate limited")
            return super().earnings(ticker)

    f = Flaky()
    first = load_earnings(["XOM"], f, str(tmp_path))
    assert first == {"XOM": []}
    second = load_earnings(["XOM"], f, str(tmp_path))
    assert second["XOM"]                                 # retried and cached this time
    assert load_earnings(["XOM"], f, str(tmp_path)) == second   # now read from the cache


def test_iv_cache_is_reused_when_dolthub_has_no_rows_for_a_ticker(tmp_path):
    class Missing(FakeFetchers):
        def dolthub(self, sql):
            return [r for r in super().dolthub(sql) if r["act_symbol"] != "CVX"]

    f = Missing()
    load_iv(["XOM", "CVX"], f, str(tmp_path), sleep=lambda s: None)
    n = f.calls["dolthub"]
    again = load_iv(["XOM", "CVX"], f, str(tmp_path), sleep=lambda s: None)
    assert f.calls["dolthub"] == n and set(again["ticker"]) == {"XOM"}


def test_drop_counts_only_count_setups_that_would_have_traded():
    f = make_panel_frame([100] * 30, start="2025-12-15", extra={"ret_5d": 0.0})
    panel = Panel({"X": f}, f.index, {"X": []})
    plan = {"family": "stock_long", "conditions": {"ret_5d": [">", 1.0]},
            "exit": {"target_pct": 0.05, "stop_pct": 0.03, "horizon_days": 5}}
    _, drops = backtest.run(panel, plan)
    assert drops["train_exit_in_2026"] == 0 and drops["validation_exit_past_data"] == 0


def test_f1_counts_trades_left_out_for_missing_coverage():
    f = make_panel_frame([100] * 40, start="2026-01-01")
    g = make_panel_frame([100] * 40, start="2026-01-01")
    panel = Panel({"X": f, "Y": g}, f.index, {"X": ["2026-01-20"], "Y": []})
    plan = {"family": "stock_long", "conditions": {}, "exit": {"target_pct": 0.05, "stop_pct": 0.03, "horizon_days": 3}}
    trades, drops = backtest.run(panel, plan, exclude_earnings=True)
    assert set(trades["ticker"]) == {"X"} and drops["f1_no_earnings_coverage"] > 0


def test_zero_implied_vol_is_skipped_not_infinite():
    f = make_panel_frame([100] * 21, start="2026-01-01")
    f["iv"], f["iv_stale"], f["iv_date"], f["earnings_within_10d"] = 0.0, False, f.index, 0.0
    trades, drops = backtest.run(Panel({"X": f}, f.index, {"X": []}), {"family": "straddle_buy", "conditions": {}})
    assert len(trades) == 0 and drops["stale_iv"] > 0


def test_jsonable_turns_nan_inf_and_nat_into_null():
    out = _jsonable({"a": np.float64("nan"), "b": np.float64("inf"), "c": -math.inf, "d": pd.NaT,
                     "e": np.int64(3), "f": pd.Timestamp("2026-01-02")})
    assert out == {"a": None, "b": None, "c": None, "d": None, "e": 3, "f": "2026-01-02T00:00:00"}
    json.dumps(out, allow_nan=False)


def test_malformed_dolthub_reply_is_retried_as_a_timeout(monkeypatch):
    monkeypatch.setattr(data.urllib.request, "urlopen", lambda *a, **k: io.BytesIO(b"<html>busy</html>"))
    with pytest.raises(TimeoutError):
        Fetchers().dolthub("SELECT 1")


def test_injected_fault_stays_labeled_injected_after_a_real_timeout():
    fetch = FakeFetchers(timeouts=1)                     # a real timeout after the injected one
    seen = []
    fetch_iv_window(fetch, ["XOM"], pd.Timestamp("2024-01-01"), pd.Timestamp("2024-01-14"), sleep=lambda s: None,
                    on_recovered=lambda *a: seen.append(a), fault=["dolthub_timeout"])
    assert seen and seen[0][2] is True


def test_reports_after_the_close_count_from_the_next_trading_day():
    idx = pd.DatetimeIndex(["2026-01-29 16:30", "2026-01-29 08:00", "2026-01-30 16:05"]).tz_localize("America/New_York")
    assert report_dates(idx) == ["2026-01-29", "2026-01-30", "2026-02-02"]   # Friday after close -> Monday


def test_refusal_with_null_fields_is_still_a_refusal(tmp_path):
    reply = {"refuse": {"is_refused": True, "reason": "insider trading"}, "family": None, "universe_group": None,
             "conditions": None, "exit": None, "hypothesis": None, "assumptions": None, "not_tested": None,
             "core_trigger_tested": None}
    fetch = FakeFetchers()
    a = Audit("ref", fake_llm(planner=reply), Tracer(), runs_dir=str(tmp_path), fetch=fetch, cache_dir=str(tmp_path / "c"))
    st = a.start("trade on a friend's tip about earnings")
    assert st["verdict"]["reason"] == "refused: insider trading" and fetch.calls["prices"] == 0


def test_missing_fields_get_one_fix_round(tmp_path):
    partial = {k: v for k, v in plan_reply().items() if k != "assumptions"}
    replies = lambda n: partial if n == 1 else plan_reply()
    a = Audit("fix", fake_llm(planner=replies), Tracer(), runs_dir=str(tmp_path), fetch=FakeFetchers(),
              cache_dir=str(tmp_path / "c"))
    st = a.start("buy dips")
    assert st["verdict"]["verdict"] != "cannot_audit"
    assert "missing fields: assumptions" in [c for c in a.llm.calls if c["role"] == "planner"][1]["prompt"]


def test_rerunning_the_report_step_adds_no_second_registry_line(tmp_path):
    a = Audit("reg", fake_llm(), Tracer(), runs_dir=str(tmp_path), fetch=FakeFetchers(), cache_dir=str(tmp_path / "c"))
    a.start("buy dips")
    a._append_registry()
    lines = [json.loads(l) for l in open(a.registry, encoding="utf-8")]
    assert [l["audit_id"] for l in lines] == ["reg"]
