# Spec: Strategy Auditor

Status: approved by the owner on 2026-10-11. Replaces the trading swarm as the main deliverable; reuses its parts.

## 1. Why

Three tests in this project found no trading edge in price, market, or volatility data (`results/README.md`, 50-stock and straddle spikes on 2026-10-10). We found that by hand: idea, data, leakage-safe backtest, baselines, statistics, follow-up test, verdict. The Strategy Auditor is a team of agents that does that work itself.

**Input:** a trading idea in plain English, e.g. "buy straddles on tech stocks before earnings".
**Output:** a verdict (`kill`, `weak`, `promising`, or `cannot_audit` when the idea doesn't fit a supported family) with an evidence report a reader can check.

Who it's for: retail and hobby traders who lose money on strategies that only looked good in a backtest.

## 2. Scope

Supported strategy families (the Planner must map every idea onto one, or say it can't):

| Family | Entry | Exit | Cost model |
|---|---|---|---|
| `stock_long` | Conditions on features (section 6) | Target %, stop %, horizon in trading days | None (no fees modeled; stated in report) |
| `straddle_buy`, `straddle_sell` | Conditions on features, including implied volatility | Hold to day 10 (fixed) | ATM straddle cost = 0.7979 × IV × √(10/252), plus 5% bid/ask haircut against the trader |

Returns per trade, payoff = |Close(t+10) / Close(t) - 1|: buyer pays the cost above, return = payoff / cost - 1. Seller receives the premium at the bid, approximated as formula × 0.95, return = (premium - payoff) / premium (losses can exceed 100% of the premium).

Out of scope: arbitrary code from the LLM, intraday data, short stock positions, live trading, crypto, any personal financial advice.

Universe: the 50 tickers from the 50-stock spike (survivorship bias stated in every report).

## 3. Splits and leakage

- Train: setups 2015-01-01 to 2025-12-31 (straddles: 2020-01-01 on, where implied vol exists), outcome window ending before 2026.
- Validation: setups 2026-01-01 to 2026-06-30. This is where verdicts are decided.
- Test: 2026-07-01 on. **The auditor never reads it.** Data fetchers stop at 2026-06-30 plus 10 trading days for outcomes.
- Features use data at or before the setup day only (existing `src/features.py` contract). Implied vol: the latest row dated on or before the setup day.

## 4. Agents and loop

```
idea
 -> Planner: idea -> AuditPlan (family, universe, conditions, exit, hypothesis, assumptions)
 -> Researcher (tools): fetch and cache data, report coverage and gaps
 -> Mathematician (code): backtest on train and validation, baselines, statistics, tail risk
 -> Naysayer: coded checks + LLM critique; may request up to 3 follow-up tests
      follow-up -> Planner revises plan -> Mathematician re-runs
 -> verdict rules (code) -> Reporter writes the report
```

| Agent | LLM? | Job |
|---|---|---|
| Planner | Yes | Translate the idea into a valid AuditPlan JSON. State every assumption it had to make. Revise on follow-up requests. |
| Researcher | Code, LLM summary | Call data tools, check coverage (rows per ticker per year), flag gaps. |
| Mathematician | No | Backtests, baselines, statistics. Deterministic. |
| Naysayer | Yes + code | Coded checks always run (section 7). LLM picks follow-ups from a fixed menu and explains doubts. |
| Reporter | Yes | Writes the report from the numbers. Cannot change the verdict. |

**Iteration cap:** at most 3 follow-up rounds per audit. Each follow-up is logged with its reason.

**Follow-up menu** (the Naysayer chooses; the Mathematician runs):
1. Re-run excluding trades whose window contains an earnings date.
2. Re-run per sub-period (each train year) to check stability.
3. Re-run with the conditions removed (is the edge from the conditions or from the family?).
4. Re-run with stricter costs (haircut 10% instead of 5%).
5. Re-run on a different exit (horizon 5 or 20 days) to check sensitivity.

## 5. AuditPlan schema

```json
{
  "family": "stock_long | straddle_buy | straddle_sell",
  "universe": ["AAPL", "MSFT"],
  "conditions": {"ret_5d": ["<", -0.03], "iv_hv_ratio": ["<", 1.0]},
  "exit": {"target_pct": 0.05, "stop_pct": 0.03, "horizon_days": 10},
  "hypothesis": "one sentence",
  "assumptions": ["'tech stocks' read as AAPL, MSFT, GOOGL, NVDA, META, AMD, ADBE, CRM, INTC, QCOM, CSCO, TXN, AVGO, IBM, ACN"]
}
```

Validation rules: family known; universe a non-empty subset of the 50 tickers; 0 to 4 conditions on known features with operators `>`, `<`, `>=`, `<=` and numeric values; `exit` required for `stock_long` (target 1–20%, stop 1–20%, horizon 1–20 days) and ignored for straddles. Invalid plans go back to the Planner once with the reason; a second invalid plan ends the audit as `cannot_audit`.

## 6. Data and tools

| Tool | Source | Notes |
|---|---|---|
| `get_prices` | Yahoo via yfinance | OHLCV for the universe plus SPY and ^VIX, cached in `data/cache/` |
| `get_implied_vol` | DoltHub `post-no-preference/options`, `volatility_history` | Query in 14-day date windows for all tickers at once (the table is keyed by date; per-ticker range queries time out). Retry with backoff; on repeated timeout, halve the window. |
| `get_earnings_dates` | yfinance `get_earnings_dates` | For the earnings follow-up and the cost caveat |
| `build_features` | `src/features.py` plus market, volume, implied-vol features from the spikes | Feature list fixed in code |
| `backtest` | `src/simulator.py` first-hit rule for `stock_long`; straddle payoff for straddles | Train and validation separately |

Every tool call is a neatlogs TOOL span. Failures are recorded, retried per the table, and reported if they persist.

## 7. Statistics, checks, verdict

Per run, train and validation separately:
- Trades `n`, win rate, mean return per trade, median, worst trade, worst 10-day window.
- Block-bootstrap 90% interval for mean return (blocks of 10 trading days; same method as `src/baselines.py`).
- Baselines on the same setups: the family with no conditions, and random selection at the same rate.

Coded Naysayer checks (always run, listed in the report):
1. `n` ≥ 30 on validation.
2. Leakage: assertions that no feature or label date is after the cutoff (fail = audit error, not a verdict).
3. Out-of-sample decay: validation mean vs train mean.
4. Multiple testing: number of plan variants tried in this audit, shown next to the result.
5. Cost realism: share of straddle trades with earnings inside the window (formula underprices those; measured up to 20% on 2026-10-10).
6. Tail risk for `straddle_sell`: worst trade and worst 10-day window, in multiples of the average premium.

**Verdict (code, not LLM):**
- `promising`: validation `n` ≥ 30, and the lower end of the 90% interval for mean return is above 0, and the mean beats the no-condition baseline.
- `weak`: validation mean above 0 but the interval includes 0, or `promising` except it fails the baseline comparison.
- `kill`: everything else, including `n` < 30.
- `promising` is downgraded to `weak` if check 6 shows a worst trade larger than 10 average premiums.

## 8. State, recovery, execution

- Each audit has `runs/audits/<audit_id>/state.json`: plan, step statuses, results so far, follow-ups used.
- `--resume <audit_id>` continues from the last finished step. Cached data is reused.
- LLM calls keep the existing wrapper: schema checks, one retry on empty or off-schema replies.
- A budget cap: at most 12 LLM calls per audit; hitting it ends the loop with the best evidence so far, stated in the report.

## 9. Output

`runs/audits/<audit_id>/report.md` with: the idea, the plan and assumptions, data coverage, results table (train, validation, baselines), checks, follow-ups with reasons, verdict, caveats, cost of the audit, neatlogs trace reference.

CLI:
```bash
python -m src.auditor "buy straddles on tech stocks before earnings"
python -m src.auditor --resume <audit_id>
```

## 10. Tracing (neatlogs)

WORKFLOW span per audit, AGENT spans per agent step, TOOL spans per data or backtest call, tags `audit_id`, `step`, `iteration`, `agent`. DeepSeek calls recorded by neatlogs' OpenAI instrumentation under the agent span (existing `src/tracing.py`).

## 11. Reuse

| From | Reused for |
|---|---|
| `src/llm.py` | All LLM calls (DeepSeek default, Claude option) |
| `src/tracing.py` | Spans |
| `src/simulator.py`, `src/labels.py`, `src/features.py` | Stock exits, adjusted High/Low, features |
| `src/tools.py` (`wilson_low`, `matches`) | Condition matching, Wilson bound |
| `src/baselines.py` (`block_bootstrap`) | Intervals |
| Spike scripts (scratchpad) | 50-stock download, DoltHub date-window fetch, straddle payoff |
| `--resume` pattern from `src/swarm.py` | Audit resume |

New files: `src/auditor/` (`plan.py`, `data.py`, `backtest.py`, `checks.py`, `verdict.py`, `report.py`, `__main__.py`), tests in `tests/test_auditor_*.py`.

## 12. Tests

- Plan validation: rejects unknown family, ticker outside the 50, 5 conditions, bad operator, out-of-range exits.
- Backtest: `stock_long` matches the first-hit rule on hand paths; straddle payoff and cost on a hand example.
- Leakage: a feature or label after the cutoff raises.
- Verdict rules: each branch on hand-made statistics, including the tail-risk downgrade.
- Follow-up cap: a Naysayer that always asks for more stops at 3.
- Resume: an audit interrupted after the backtest resumes without refetching data or re-calling the Planner.
- DoltHub fetch: a fake API that times out on 14-day windows gets halved windows and succeeds.

## 13. Evidence plan (hackathon checklist)

- **Agent improved:** run the same three demo ideas before and after adding the Naysayer follow-ups; compare verdicts, number of tests, and cost per audit from neatlogs traces.
- **Recovery:** the DoltHub timeout path (section 6) in a real run, visible in traces.
- **neatlogs, Entire, cfo.ai:** traces for each demo audit; Entire checkpoints on the auditor commits; cfo.ai plan priced per audit using measured cost per audit.

Demo ideas: (1) "buy dips in an uptrend" (expected `kill`); (2) "buy straddles on tech before earnings" (expected `kill`, with the earnings cost caveat); (3) "sell straddles on low-volatility mega-caps" (expected positive mean; tail-risk check decides between `weak` and `promising`). Expectations are written here before any run.

## 14. Decisions to confirm

1. Three strategy families only (section 2).
2. Verdicts decided on validation; test never read.
3. Verdict rules in code; LLMs explain but cannot override (section 7).
4. Follow-up cap 3, LLM budget 12 calls per audit (sections 4, 8).
5. Universe fixed to the 50 tickers.
6. The trading swarm stays in the repo as a component and as prior work; the auditor is the submission's main agent.
