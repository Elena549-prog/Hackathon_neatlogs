# Strategy Auditor: how to run it

Built from `docs/AUDITOR_SPEC.md` (revision 2) on branch `auditor`. Covers milestones M1 and M2: plan, data, backtest, verdict, follow-ups F1–F4, events, report, CLI. Not built yet: the web interface (section 16, M3) and Laya triage (section 15, stretch).

## Status

- **Tested with fakes only.** 200 tests pass (`python -m pytest tests/ -q`), including the spec section 12 list, on synthetic prices and fake LLMs. It has **not** run against Yahoo, DoltHub or DeepSeek yet: the workspace it was built in can't reach them. The first real run is the real test.
- Keys: `DEEPSEEK_API_KEY` (or `ANTHROPIC_API_KEY` with `--provider claude`), `NEATLOGS_API_KEY`. Load `.env` as in `docs/STATUS.md`.

## Commands

```bash
# M1 "before" runs: no follow-ups (Planner + Reporter: 2 LLM calls)
python -m src.auditor --no-followups --save-demo "buy dips in an uptrend"
# M2 "after" runs: Naysayer picks follow-ups (up to 5 LLM calls)
python -m src.auditor --save-demo "buy straddles on tech stocks before earnings"
python -m src.auditor --save-demo "sell straddles on low-volatility mega-caps"
# recovery evidence (labeled INJECTED in the report)
python -m src.auditor --fault dolthub_timeout "buy straddles on tech stocks before earnings"
python -m src.auditor --fault llm_empty "buy dips in an uptrend"
# continue an interrupted audit (no re-plan, no refetch)
python -m src.auditor --resume <audit_id>
```

Outputs: `runs/audits/<id>/` (`events.jsonl`, `state.json`, `report.md`), the registry `runs/audits/registry.jsonl`, and with `--save-demo` a committable copy in `results/audits/<id>/`.

## First real run: what to expect

- **Data, first run only:** one yfinance download for the group's tickers plus SPY and ^VIX (2014 to 2026-07-29), cached in `data/cache/prices/`; earnings dates for each ticker (50 calls for `all_50`), cached in `data/cache/earnings.json`. Later audits read the cache.
- **Implied vol:** reuses `data/cache/iv_50.csv` (the straddle spike's cache) when it covers the group and window, so the straddle demos make no DoltHub calls except the one `--fault dolthub_timeout` window. Without that file it fetches about 185 fourteen-day windows and writes `data/cache/iv_auditor.csv`.
- **Balance check:** DeepSeek's `/user/balance` before a real audit; refuses under $2, warns if it can't read it. `--skip-balance-check` to skip.

## Things to check on the first real run

1. yfinance column layout for a multi-ticker download (`Fetchers.prices`): every ticker should have Open/High/Low/Close/Adj Close/Volume.
2. `get_earnings_dates(limit=60)` coverage: the report lists each ticker's earliest earnings date. Tickers without dates are left out of F1 and priced without the earnings factor (counted in the report).
3. The neatlogs trace: one WORKFLOW span `audit` per audit with AGENT and TOOL spans tagged `audit_id`, `step`, `followup`; `trace_id` in the `audit_started` and `report_ready` events (format of the trace URL still to verify, spec section 10).
4. Cost per audit from the report's "Cost of this audit" section, for the cfo.ai model.

## Interpretation choices (flag if you disagree)

- **Which setups exist** is decided by the horizon end, not the actual exit (train setups dropped when the horizon ends in 2026; validation setups dropped when it runs past the data). The actual exit can be earlier; using it would make the setup set depend on the outcome.
- **One open trade per ticker:** a new entry is taken on a day strictly after the previous trade's exit day.
- **Earnings features** are NaN before a ticker's earliest known report date and for tickers with no coverage; a missing feature never matches a condition.
- **SPY and ^VIX features** use Adj Close, as in the spike scripts.
- **Random-selection baseline** draws each setup with probability (v0 trades / baseline trades), then applies the same one-trade-per-ticker rule. Reported only.
- **`--fault dolthub_timeout`** fires on the first DoltHub fetch even when the implied vol is cached, so the recovery always shows. It only applies to straddle ideas; for `stock_long` a note says it wasn't triggered.
- **Coded checks** are emitted as `check_result` events with agent `naysayer` (they are the Naysayer's coded checks in the spec).
