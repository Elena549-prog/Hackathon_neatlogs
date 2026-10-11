# Spec: Strategy Auditor

Status: approved by the owner on 2026-10-11; revision 2 (same day) applies the review patches listed in section 19.

Replaces the trading swarm as the main deliverable; reuses its parts.

## 1. Why

Three tests in this project found no trading edge in the price, market and volatility features and the strategy families we tested (`results/README.md`, 50-stock and straddle spikes on 2026-10-10). We found that by hand: idea, data, leakage-safe backtest, baselines, statistics, follow-up test, verdict. The Strategy Auditor is a team of agents that does that work itself.

**Input:** a trading idea in plain English, e.g. "buy straddles on tech stocks before earnings".
**Output:** a verdict with an evidence report a reader can check.

| Verdict | Meaning |
|---|---|
| `kill` | Enough evidence, and the validation mean return per trade is 0 or below. |
| `inconclusive` | Not enough evidence, or positive but not convincing. A strategy with no real edge lands here about half the time. |
| `promising` | Passed every rule in section 7 on a 6-month historical screen. Not a forecast. |
| `cannot_audit` | Refused, outside the supported families, core of the idea not testable, or no valid plan. |

Who it's for: retail and hobby traders who lose money on strategies that only looked good in a backtest.

## 2. Scope

Supported strategy families (the Planner must map every idea onto one, or say it can't):

| Family | Entry | Exit | Cost model |
|---|---|---|---|
| `stock_long` | Conditions on features (section 6) | Target %, stop %, horizon in trading days; gap fills at the Open (below) | None (no fees modeled; stated in report) |
| `straddle_buy`, `straddle_sell` | Conditions on features, including implied volatility | Hold to day 10 (fixed) | ATM straddle formula = 0.7979 × IV × √(10/252). Buyer pays formula × 1.05 (5% bid/ask haircut), and that cost × 1.20 when an earnings date falls inside the 10-day window. Seller receives formula × 0.95. |

Straddle returns per trade. Payoff = |Close(t+10) / Close(t) - 1|, on split-adjusted Close (yfinance `Close` with `auto_adjust=False`), not dividend-adjusted `Adj Close`. Buyer: return = payoff / cost - 1. Seller: return = (premium - payoff) / premium (losses can exceed 100% of the premium). The × 1.20 earnings factor is measured: real asks were up to 1.20 × formula around earnings (2026-10-10). The 1.20 is measured against the formula including the 1.05 haircut (the calibration compared real asks to 0.7979 × IV × √T × 1.05), so buyer cost around earnings = formula × 1.05 × 1.20. Section 7 adds a stricter-cost check on top.

**Trade rules.**
- One open trade per ticker at a time. A new entry for a ticker is taken only after its previous trade has closed. `n` counts these trades.
- Straddles: skip a trade when the latest implied-vol row on or before the setup day is more than 5 calendar days old. DoltHub has Monday, Wednesday and Friday rows in 2020–2024 and daily rows from 2025. The report counts skipped trades.
- `stock_long`: entry at the setup day's Adj Close. Stop and target are absolute prices, `entry × (1 - stop_pct)` and `entry × (1 + target_pct)`. High, Low and Open are scaled to the Adj Close scale (same factor as `src/labels.py` `adjusted_high_low`). On each day after entry: if the Open is at or below the stop, exit at the Open; if the Open is at or above the target, exit at the Open; otherwise the swarm's first-hit rule applies (stop first when both are hit on the same day). No hit by the horizon: exit at that day's close. The swarm's simulator is unchanged; the auditor has its own gap-aware version.

Out of scope: arbitrary code from the LLM, intraday data, short stock positions, live trading, crypto, position sizing, any personal financial advice.

**Universe groups.** The Planner picks one group name; it never lists tickers. Groups are fixed in code from the 50 tickers of the 50-stock spike, as of 2025-12-31 (survivorship bias stated in every report). Sector groups follow standard GICS sectors, and each ticker is in exactly one of them.

| Group | Tickers | Count |
|---|---|---|
| `all_50` | AAPL, MSFT, GOOGL, AMZN, NVDA, META, TSLA, BRK-B, JPM, V, JNJ, UNH, XOM, PG, MA, HD, CVX, MRK, ABBV, PEP, KO, AVGO, COST, LLY, WMT, BAC, PFE, TMO, CSCO, MCD, ABT, CRM, DIS, ACN, ADBE, NFLX, WFC, TXN, NKE, AMD, INTC, QCOM, HON, UNP, IBM, CAT, GS, BA, AMGN, SBUX | 50 |
| `tech` (information technology plus communication services) | AAPL, MSFT, NVDA, AVGO, CSCO, CRM, ACN, ADBE, TXN, AMD, INTC, QCOM, IBM, GOOGL, META, NFLX, DIS | 17 |
| `financials` | BRK-B, JPM, V, MA, BAC, WFC, GS | 7 |
| `healthcare` | JNJ, UNH, MRK, ABBV, LLY, PFE, TMO, ABT, AMGN | 9 |
| `energy` | XOM, CVX | 2 |
| `consumer` (staples plus discretionary) | AMZN, TSLA, HD, MCD, NKE, SBUX, PG, KO, PEP, COST, WMT | 11 |
| `industrials` | HON, UNP, CAT, BA | 4 |
| `mega_cap` (approximate, fixed list: the 10 largest by market cap at end-2025) | AAPL, MSFT, NVDA, GOOGL, AMZN, META, AVGO, TSLA, BRK-B, LLY | 10 |

The six sector groups split the 50 tickers with no overlap; `all_50` and `mega_cap` overlap them.

`energy` (2 tickers) and `industrials` (4) will usually end `inconclusive` for lack of trades (section 7 needs validation `n` ≥ 30 with one open trade per ticker). When the plan uses one of them, the report says so before the results.

## 3. Splits, data windows and leakage

This section overrides `docs/SPEC.md` section 0 for the auditor.

| Split | Setups | Rule |
|---|---|---|
| Train | 2015-01-01 to 2025-12-31 (straddles: 2020-01-01 on, where implied vol exists) | A setup is dropped if its exit date is on or after 2026-01-01. |
| Validation | 2026-01-01 to 2026-06-30 | Verdicts are decided here. Setups whose exit falls past the fetched data are dropped and counted in the report. |
| Test | 2026-07-01 or later | Never constructed. Never read by the auditor or the agents. After the hackathon, one code-only run may check plans registered as `promising` on the test window, once, with frozen plans; results are never fed back to the agents. |

**Data windows.**
- Prices (universe, SPY, ^VIX): 2014-01-01 to an exclusive end of 2026-07-30. That is 20 trading days after 2026-06-30, enough for the longest exit. Prices after 2026-06-30 are used only for validation exits.
- Implied vol: 2019-06-01 to 2026-06-30.
- Earnings dates: section 6.

**Leakage.**
- Features use data at or before the setup day only (`src/features.py` contract). Implied vol: the latest row dated on or before the setup day, and no more than 5 calendar days old (section 2).
- Exception: the two earnings features use actual report dates (section 6). Companies usually announce dates weeks ahead, so the look-ahead is small but not zero. They are exempt from the leakage assertion for that reason only, and every report that uses them says so.
- The auditor must not import `TICKERS`, `split_for`, `load_market` or `load_prices` from `src/data.py`, `src/labels.py` or `src/tools.py`. Those encode the swarm's frozen 5-ticker splits.

**Shared validation window.** Every audit uses the same 6 months. A global registry, `runs/audits/registry.jsonl`, gets one line per finished audit: date, idea, family, universe group, plan hash, verdict. Every report prints how many audits have used this validation window and the line: "About 5% of plans with no real edge pass this test by chance; testing many variants of one idea raises that."

## 4. Agents and loop

```
idea
 -> Planner (LLM): idea -> AuditPlan v0, or a refusal
      refused                    -> cannot_audit "refused" (no data fetch, no backtest)
      invalid twice              -> cannot_audit "no valid plan"
      core_trigger_tested false  -> cannot_audit "core of the idea not testable with available data"
 -> freeze v0: plan JSON and its SHA-256 hash go into state.json and the report
 -> Researcher (code): fetch and cache data, report coverage and gaps
 -> Mathematician (code): backtest v0 on train and validation, no-condition baseline,
      statistics, stricter-cost check (straddles), tail risk
 -> Naysayer (LLM call 1): states doubts, picks up to 3 follow-ups from F1-F4
 -> Mathematician (code): runs the chosen follow-ups on v0
 -> Naysayer (LLM call 2): final critique
 -> verdict rules (code)
 -> report template (code) + Reporter prose (LLM, optional)
```

**The frozen plan.** The Planner's first valid plan (v0) is frozen before any backtest: its JSON and SHA-256 hash go into `state.json` and the report. Only v0's results produce the verdict. There are no plan revisions. Follow-ups are robustness checks applied in code to v0, with no Planner call.

| Agent | LLM calls | Job |
|---|---|---|
| Planner | Up to 2: the initial plan, plus one fix after an invalid plan | Translate the idea into a valid AuditPlan JSON, or refuse it. State every assumption and every part of the idea it could not express (section 5). |
| Researcher | 0 (code summary) | Call data tools, check coverage (rows per ticker per year), flag gaps. |
| Mathematician | 0 | Backtests, baselines, statistics, follow-ups. Deterministic. |
| Naysayer | 2 | Coded checks always run (section 7). Call 1, after the base results: choose follow-ups and state doubts. Call 2, after the follow-ups: final critique. Cannot change the verdict. |
| Reporter | 1, reserved (the 8th call) | Adds explanation prose to the code-written report (section 9). Cannot change the verdict or any number. If the Reporter call errors, the template ships without prose. |

The budget is 8 LLM calls per audit (section 8). The 8th call is reserved for the Reporter; all other roles together may use at most 7. The roles above use at most 5.

**Refusal.** The Planner's output includes `refuse` (section 5). It refuses market manipulation, trading on non-public information, and anything illegal. A refused idea ends as `cannot_audit` with reason "refused": no data fetch, no backtest. The Laya guardrail (section 15) is an optional extra layer, not the only one.

**Follow-up menu.** The Naysayer picks up to 3 that apply; the Mathematician runs them on v0 in code. Follow-ups can only downgrade `promising` to `inconclusive`; they never change any other verdict. An inconclusive verdict caused by thin evidence must not become `kill`; follow-ups are robustness checks for a positive result. Each follow-up is logged with the Naysayer's reason, its result, and any downgrade.

| ID | Follow-up | Families | Downgrade if |
|---|---|---|---|
| F1 | Earnings excluded: re-run without trades whose holding window contains an earnings date. The holding window is the trade's own: 10 trading days for straddles, the plan's `horizon_days` for `stock_long`. | All. Needs earnings data; skipped with a note if missing. Trades on tickers without earnings coverage are left out, with the count reported. | The validation mean becomes ≤ 0. |
| F2 | Per-year stability: train mean per calendar year | All | The yearly train mean has the opposite sign to the validation mean in more than half the train years. |
| F3 | Horizon sensitivity: horizons 5 and 20 days | `stock_long` only | Both have validation mean ≤ 0. |
| F4 | Concentration: re-run without the single ticker that contributes most to validation profit | All | The validation mean becomes ≤ 0. |

The no-condition baseline comparison and, for straddles, the stricter-cost check are not follow-ups. They are always computed as part of the verdict (section 7).

## 5. AuditPlan schema

The Planner sees the idea text, the universe group names with their tickers (section 2), and the feature list (section 6). It never sees dates.

Stored plan (map form):

```json
{
  "refuse": {"is_refused": false, "reason": ""},
  "family": "stock_long | straddle_buy | straddle_sell",
  "universe_group": "all_50",
  "conditions": {"ret_5d": ["<", -0.03], "close_to_ma200": [">", 1.0]},
  "exit": {"target_pct": 0.05, "stop_pct": 0.03, "horizon_days": 10},
  "hypothesis": "one sentence",
  "assumptions": ["'uptrend' read as close above its 200-day average", "'dip' read as a 5-day return below -3%"],
  "not_tested": [],
  "core_trigger_tested": true
}
```

In the LLM's reply schema, `conditions` is a list, `[{"feature": ..., "op": ..., "value": ...}]`, as `src/agents/planner.py` does. Code converts it to the map form above. Plan v0 is the validated map form, serialized as canonical JSON (sorted keys); its hash is the SHA-256 of that text.

Fields:
- `refuse`: `is_refused` true, with a reason, for market manipulation, non-public information, or anything illegal. When true, the other fields are ignored.
- `universe_group`: one of the 8 group names in section 2.
- `not_tested`: parts of the idea that could not be expressed with the available families and features (e.g. "news sentiment").
- `core_trigger_tested`: false when the part of the idea that triggers a trade could not be expressed. The audit then ends as `cannot_audit` with reason "core of the idea not testable with available data".

**Validation rules** (in `plan.py`; `src/llm.py` `schema_error` only checks top-level keys, so nested fields are checked here): family known; `universe_group` one of the 8 names; 0 to 4 conditions on features from the section 6 table, with operators `>`, `<`, `>=`, `<=` and numeric values; implied-vol features rejected for `stock_long`; `exit` required for `stock_long` (target 1–20%, stop 1–20%, horizon 1–20 days) and ignored for straddles; `not_tested` a list of strings; `core_trigger_tested` a boolean. An invalid plan goes back to the Planner once with the reason; a second invalid plan ends the audit as `cannot_audit`.

**"What was tested" line.** Code, not the LLM, writes it from the plan JSON, e.g. "stock_long on all_50 (50 tickers): enter when ret_5d < -0.03 and close_to_ma200 > 1.0; exit at +5% / -3% / 10 days. Not tested: nothing." It is shown at the top of the report and in the UI.

## 6. Data and tools

| Tool | Source | Notes |
|---|---|---|
| `get_prices` | Yahoo via yfinance, `auto_adjust=False` (gives both `Close` and `Adj Close`) | OHLCV for the group's tickers plus SPY and ^VIX, 2014-01-01 to 2026-07-30 (exclusive), cached in `data/cache/` |
| `get_implied_vol` | DoltHub `post-no-preference/options`, `volatility_history` | 2019-06-01 to 2026-06-30. Query in 14-day date windows for all tickers at once (the table is keyed by date; per-ticker range queries time out). Retry with backoff; on repeated timeout, halve the window. |
| `get_earnings_dates` | yfinance `get_earnings_dates(limit=60)` | Cached. The report lists each ticker's earliest available date. Tickers without coverage get NaN earnings features and their trades are left out of F1, with the count reported. |
| `build_features` | `src/features.py` plus the market, volume, implied-vol and earnings features below | Feature list fixed in code |
| `backtest` | Section 2 trade rules: gap-aware first-hit for `stock_long`, straddle payoff for straddles | Train and validation separately |

**Features the Planner may use.** Formulas match `src/features.py` and the spike scripts in `scripts/spikes/`.

| Kind | Feature | Formula | Families |
|---|---|---|---|
| Price | `ret_1d`, `ret_5d`, `ret_10d`, `ret_20d` | Adj Close today / Adj Close N trading days ago - 1 | All |
| Price | `vol_20d` | Standard deviation of the last 20 daily returns | All |
| Price | `close_to_ma50`, `close_to_ma200` | Adj Close today / mean Adj Close of the last 50 or 200 days (today included) | All |
| Market | `spy_ret_5d`, `spy_ret_20d` | SPY close today / SPY close N trading days ago - 1 | All |
| Market | `spy_close_to_ma50` | SPY close / its 50-day mean | All |
| Market | `vix_level` | ^VIX close | All |
| Market | `vix_chg_5d` | ^VIX today / ^VIX 5 trading days ago - 1 | All |
| Market | `rel_ret_20d` | `ret_20d` - `spy_ret_20d` | All |
| Volume | `vol_ratio_5d`, `vol_ratio_20d` | Today's volume / mean volume of the previous 5 or 20 days | All |
| Implied vol | `iv` | DoltHub `iv_current` | Straddles only |
| Implied vol | `hv` | DoltHub `hv_current` | Straddles only |
| Implied vol | `iv_hv_ratio` | `iv` / `hv` | Straddles only |
| Implied vol | `iv_minus_rv20` | `iv` - `vol_20d` × √252 | Straddles only |
| Earnings | `earnings_within_10d` | 1 if a report date falls in the next 10 trading days, else 0 | All |
| Earnings | `days_since_earnings` | Trading days since the last report date | All |

The plan validator rejects implied-vol features for `stock_long`.

**Earnings caveat**, printed in every report that uses an earnings feature or F1: actual report dates are used; companies usually announce dates weeks ahead, so the look-ahead is small but not zero.

**Failures.** Every tool call is a neatlogs TOOL span. Failures are recorded, retried per the table, and reported if they persist.

**Fault injection** (recovery evidence). `--fault dolthub_timeout` makes the first DoltHub fetch raise a timeout. `--fault llm_empty` makes the first LLM reply empty. The recovery emits a `recovered` event with `"injected": true`, and the UI and report label it INJECTED. Recoveries from real failures carry `"injected": false` and are labeled REAL.

## 7. Statistics, checks, verdict

Per run (v0, the no-condition baseline, each follow-up), train and validation separately:
- Trades `n` (one open trade per ticker, section 2), number of distinct 10-trading-day blocks with at least one entry, win rate, mean return per trade, median, worst trade, worst 10-trading-day window of summed trade returns.
- A 95% interval for the mean from `bootstrap_mean(dates, returns)`: block bootstrap over 10-trading-day blocks of entry dates, 2000 resamples, reporting the 2.5th and 97.5th percentiles. The "lower bound" is the 2.5th percentile.
- Baselines on the same family, universe group, period and trade rules: the family with no conditions (used by the verdict), and random selection at the same rate (reported only).

`bootstrap_mean` is new. `src/baselines.py` `block_bootstrap` computes AUC and Brier for binary labels and can't be reused for means. `src/tools.py` `wilson_low` is not used here.

**Paired baseline test.** Resample the same blocks for v0 and the no-condition baseline, and take the 2.5th percentile of (v0 mean minus baseline mean) on validation. This is the paired lower bound.

**Stricter-cost check** (straddles, always run). Buyer cost +10% and seller premium -10%, on top of the section 2 costs. A plan survives the stricter-cost check if, under the stricter costs, the lower bound of the validation mean stays above 0.

**Tail risk.** Computed on train plus validation combined (train includes March 2020): the worst single trade and the worst 10-trading-day window of summed trade returns. For `straddle_sell`, losses are reported as multiples of the average premium and as % of stock price, and a `promising` becomes `inconclusive` if either:
- the worst single trade loses more than 5 average premiums, or
- the loss in the worst 10-trading-day window is larger than the total validation gain (sum of validation trade returns).

For the other families, the worst trade and worst window are reported with no downgrade.

**Coded Naysayer checks** (always run, listed in the report):
1. Evidence: validation `n` ≥ 30 and trades in at least 6 distinct 10-trading-day blocks.
2. Leakage: assertions that no feature or label date is after the cutoff (fail = audit error, not a verdict). The two earnings features are exempt (section 3).
3. Out-of-sample decay: validation mean vs train mean.
4. Shared window: number of audits in the registry that used this validation window, with the 5% line (section 3).
5. Cost realism: share of straddle trades with an earnings date inside the window (priced at × 1.20), and the stricter-cost result.
6. Tail risk, as above.
7. Data drops: train setups dropped for exits in 2026, validation setups dropped for exits past the data, straddle trades skipped for stale implied vol, trades left out of F1 for missing earnings coverage.

**Verdict (code, not LLM)**, in this order:
1. `cannot_audit` if the plan was refused, invalid twice, or has `core_trigger_tested` false. No backtest is run.
2. `inconclusive` (not enough evidence) if validation `n` < 30 or the trades fall in fewer than 6 distinct blocks.
3. `kill` if there is enough evidence and the validation mean is ≤ 0.
4. `promising` only if all of these hold:
   - lower bound of the validation mean > 0;
   - paired lower bound of (v0 minus no-condition baseline) > 0, same family, same universe group, same period;
   - train mean > train baseline mean;
   - straddles: passes the stricter-cost check;
   - passes the tail-risk rule;
   - not downgraded by a follow-up (section 4).
5. `inconclusive` otherwise.

Reports describe `inconclusive` as "inconclusive: a strategy with no real edge lands here about half the time".

## 8. State, recovery, execution

- Each audit has `runs/audits/<audit_id>/state.json`: plan v0 and its hash, step statuses, results so far, follow-ups chosen and run, LLM calls used, and the next event `seq`.
- `--resume <audit_id>` continues from the last finished step and continues the event `seq`. Cached data is reused. v0 is never re-planned.
- LLM calls keep the existing wrapper: schema checks, one retry on empty or off-schema replies.
- **Budget:** at most 8 LLM calls per audit. The 8th call is reserved for the Reporter; all other roles together may use at most 7. Each `llm()` invocation counts as one call. Internal retries don't count as extra calls, but their tokens and cost are counted. The count is persisted in `state.json` and checked before every call. Hitting the 7-call cap for the other roles ends the loop with the evidence so far: the verdict rules run on what exists, the Reporter still gets its reserved call, and the report says the cap was hit. If the Reporter call errors, the template ships without prose.
- **Cost per audit:** estimated before M1 as (calls per audit) × (average cost per call from neatlogs); measured at M1 from neatlogs traces.
- **DeepSeek balance:** before a real audit, `__main__` checks the DeepSeek account balance (through DeepSeek's balance API if available, otherwise a manual check documented in the runbook, `docs/STATUS.md` "Running things") and refuses to start below $2. Tests and development runs use a fake LLM. At most 25 real audits before the freeze. A top-up before M1 is recommended, not required.
- **Demo audits** are copied to `results/audits/<audit_id>/` (`events.jsonl`, `report.md`, `state.json`) so they can be committed; `runs/` is gitignored.

## 9. Output

`runs/audits/<audit_id>/report.md`, built from a code template. Code writes the "What was tested" line, the verdict, every number, the caveats and the disclaimer. The Reporter only adds explanation prose.

Report contents, in order:
1. What was tested (section 5) and the verdict. `promising` carries the subtitle "Passed a 6-month historical screen. Not a forecast. Not financial advice." `inconclusive` carries "inconclusive: a strategy with no real edge lands here about half the time".
2. The idea, plan v0 with its SHA-256 hash, assumptions, and `not_tested`.
3. Data coverage, including earnings coverage and the drop counts (section 7, check 7).
4. Results table: train, validation, no-condition baseline, paired difference, stricter cost (straddles), tail risk.
5. Coded checks and follow-ups, with reasons, results, and any downgrade.
6. How many audits have used this validation window, and the 5% line (section 3).
7. The Naysayer's final critique and the Reporter's prose, if any.
8. Recoveries, each labeled REAL or INJECTED.
9. Cost of the audit (LLM calls, tokens, $) and the neatlogs trace reference.
10. Footer: not financial advice; survivorship bias (today's large caps); one validation window; costs approximated.

**Prose check.** The Reporter's prose is checked against a banned-phrase list: "will profit", "guaranteed", "risk-free", "we recommend", "you should buy", "you should sell", "sure thing". If any appear, the template ships without prose. No position sizing anywhere.

On finishing, the audit appends its line to `runs/audits/registry.jsonl` (section 3).

CLI:
```bash
python -m src.auditor "buy straddles on tech stocks before earnings"
python -m src.auditor --id <audit_id> "<idea>"            # used by the server (section 16)
python -m src.auditor --resume <audit_id>
python -m src.auditor --fault dolthub_timeout "<idea>"    # or --fault llm_empty (section 6)
```

## 10. Tracing (neatlogs)

WORKFLOW span per audit, AGENT spans per agent step, TOOL spans per data or backtest call, tags `audit_id`, `step`, `followup` (F1–F4, when running a follow-up), `agent`. DeepSeek calls recorded by neatlogs' OpenAI instrumentation under the agent span (existing `src/tracing.py`). The trace id comes from the OpenTelemetry span context and goes into the `audit_started` and `report_ready` events (section 16); the trace URL format is to be verified during the build.

## 11. Reuse

| From | Reused for |
|---|---|
| `src/llm.py` | All LLM calls (DeepSeek default, Claude option); changes below |
| `src/tracing.py` | Spans; `llm_call` events through a callback on Tracer spans (section 16) |
| `src/simulator.py` (`first_hit`) | Reference for the auditor's gap-aware stock exit. `first_hit` takes absolute entry, stop and target prices, not percentages, and has no gap rule. |
| `src/labels.py` (`adjusted_high_low`), `src/features.py` | Adjusted High/Low (and the same factor for Open), price features |
| `src/tools.py` (`matches`) | Condition matching on the map form |
| Spike scripts in `scripts/spikes/` (CSV caches in `data/cache/`) | 50-stock download, DoltHub date-window fetch, straddle payoff, market and volume features |
| `--resume` pattern from `src/swarm.py` | Audit resume |

Not reused: `src/baselines.py` `block_bootstrap` (AUC/Brier for binary labels; mean intervals use the new `bootstrap_mean`, section 7); `src/tools.py` `wilson_low` (not used by section 7); `TICKERS`, `split_for`, `load_market`, `load_prices` (section 3).

**Required changes to existing code.**
- `src/llm.py`: `MODELS` and `DEEPSEEK_THINKING` need entries for `reporter` (`deepseek-flash`, thinking off) and for `triage` if used. `MODELS` is keyed by provider, so the `claude` provider needs matching entries.
- Passing `agent=` as a tag raises `TypeError` today (`llm()` passes `agent=agent` and `**tags` to the same span), so the auditor's wrapper must not pass `agent` twice.
- `schema_error` only checks top-level keys, so `plan.py` does the nested validation (section 5).
- The LLM schema for conditions uses the list form `[{feature, op, value}]`, as `src/agents/planner.py` does; code converts it to the map form.
- `src/tracing.py`: the Tracer needs a callback on spans to emit `llm_call` events (section 16).

New files: `src/auditor/` (`plan.py`, `data.py`, `backtest.py`, `checks.py` with `bootstrap_mean`, `verdict.py`, `report.py`, `__main__.py`, `server.py` for section 16, `triage.py` for section 15 if built), tests in `tests/test_auditor_*.py`. Build task: `requirements.txt` (fastapi, uvicorn, plus the existing dependencies).

## 12. Tests

- Plan validation: rejects unknown family, unknown universe group (including a ticker list in place of a group), 5 conditions, bad operator, out-of-range exits, and implied-vol features for `stock_long`; converts list-form conditions to the map form.
- Plan freeze: v0's JSON and SHA-256 hash are in `state.json` before any backtest; the report prints the same hash; no Planner call after v0.
- Refusal: a refused idea ends as `cannot_audit` "refused" with zero data fetches and zero backtests.
- Core trigger: `core_trigger_tested` false ends as `cannot_audit` with the stated reason.
- Backtest: `stock_long` matches the first-hit rule on hand paths; gap fills at the Open (Open below the stop, Open above the target); one open trade per ticker; straddle payoff and cost on a hand example, including the × 1.20 earnings cost and the stale implied-vol skip.
- Leakage: a feature or label after the cutoff raises; the earnings features are exempt.
- Statistics: `bootstrap_mean` on a hand example; the paired baseline lower bound on hand-made trades.
- Verdict rules, each branch on hand-made statistics: `inconclusive` for `n` < 30 and for fewer than 6 blocks; `kill`; `promising`; `inconclusive` otherwise; failing the paired baseline test; failing the stricter-cost check; the tail-risk rule (worst trade over 5 premiums, worst window over the total validation gain).
- Follow-ups: they only downgrade `promising` to `inconclusive`; a failed follow-up leaves `inconclusive` and `kill` unchanged; a Naysayer asking for more than 3 gets 3; F3 is not run for straddles.
- Budget: a fake LLM is refused after 7 non-Reporter calls; the Reporter's reserved 8th call still runs and the report says the cap was hit; a Reporter call that errors ships the template without prose.
- Prose check: Reporter prose with a banned phrase is dropped.
- Fault injection: `--fault dolthub_timeout` and `--fault llm_empty` produce `recovered` events with `"injected": true`, labeled INJECTED in the report.
- Resume: an audit interrupted after the backtest resumes without refetching data or re-calling the Planner, and continues the event `seq`.
- DoltHub fetch: a fake API that times out on 14-day windows gets halved windows and succeeds.

## 13. Evidence plan (hackathon checklist)

- **Agent improved:** the same three demo ideas at M1 (tag `before`, no follow-ups) and at M2 (tag `after`, follow-ups and downgrade rules), compared on metrics fixed in section 17: verdict per idea, downgrades with reasons, LLM calls, cost and wall time per audit (from neatlogs). We claim no more than that table shows. Fallback evidence that already exists: swarm cost per setup $0.038 → $0.0066 (`docs/SWARM_SPEC.md` section 15; before/after files and method in `results/swarm_cost_cut/`).
- **Recovery:** the DoltHub timeout path (section 6), visible in traces. Real failures are labeled REAL; `--fault` runs are labeled INJECTED.
- **neatlogs:** traces for each demo audit.
- **Entire:** checkpoints on the auditor commits (section 17, M0).
- **cfo.ai:** the business plan is built at M0, priced per audit, using the estimated cost per audit (section 8), flagged as an estimate. The single cost variable is updated after M2 with the measured figure. `results/business_model.xlsx` was reworked for per-audit pricing on 2026-10-11 (estimate $0.048 per audit, `Assumptions!B5`; see `docs/CFO_AI.md`).
- **Video** (about 3 minutes). Beats: idea typed → agents at work (replay) → a recovery (labeled) → verdict stamp → neatlogs trace → Entire checkpoint → cfo.ai plan → before/after table. If the interface isn't ready, record the terminal, the report and neatlogs instead. Suggested owner: Elena (team to confirm).
- **Posts:** tagged #neatHack, scheduled in section 17.

Demo ideas: (1) "buy dips in an uptrend" (expected `kill`); (2) "buy straddles on tech before earnings" (expected `kill`, with the earnings cost caveat); (3) "sell straddles on low-volatility mega-caps" (expected positive mean; tail-risk check decides between `inconclusive` and `promising`). Expectations are written here before any run.

## 14. Decisions to confirm

1. Three strategy families only (section 2).
2. Verdicts decided on validation from the frozen plan v0; the test window is never read by the auditor or the agents (section 3).
3. Verdict rules in code; LLMs explain but cannot override (section 7).
4. Follow-ups F1–F4, up to 3, downgrade `promising` to `inconclusive` only; LLM budget 8 calls per audit (sections 4, 8).
5. Universe fixed to the 50 tickers, chosen through fixed groups (section 2).
6. The trading swarm stays in the repo as a component and as prior work; the auditor is the submission's main agent.
7. Laya triage and guardrail are a stretch goal, zero-shot only, `τ_guard` fixed at 0.9, `τ_triage` by leave-one-out on 50 labeled ideas (section 15).
8. Mission-control web interface: FastAPI + React/Vite/Tailwind/Framer Motion/lightweight-charts, driven only by the audit event stream, with replay mode for the video (section 16).

## 15. Stretch goal: Laya triage and guardrail (owner, 2026-10-11)

Start only after milestone M2 (section 17) is done and at least 8 hours remain before the freeze. First item to cut if time is short; the submission is complete without it. The Planner's own refusal (section 4) is the main guardrail; Laya is an optional extra layer.

**What it does.** Before the Planner runs, Laya (https://github.com/NandhaKishorM/laya, Apache-2.0) makes two fast typed decisions on the raw idea text:

| Decision | Laya type | Question | Answers |
|---|---|---|---|
| Guardrail | `noul` | "Is this a request to test a legal trading strategy on historical data?" | yes / no, with confidence |
| Triage | `choice` | "Which strategy family does this idea describe?" | `stock_long`, `straddle_buy`, `straddle_sell`, `out_of_scope` |

**Routing.**
- Guardrail `no` with confidence ≥ `τ_guard` (0.9) → stop. Verdict `cannot_audit`, reason "refused by guardrail". No LLM call.
- Triage `out_of_scope` with confidence ≥ `τ_triage` → stop. Verdict `cannot_audit`, reason "outside supported families". No LLM call.
- Triage family with confidence ≥ `τ_triage` → pass it to the Planner as a hint. The Planner may disagree but must say why in `assumptions`.
- Any confidence below threshold → the Planner decides alone, exactly as without Laya.
- Laya unavailable (error or timeout over 5 s) → skip triage, log it as a recovered failure, continue with the Planner.

Laya can stop an audit only through the two refusal rules. It never changes a verdict.

**Evaluation (written before measuring).**
- A labeled set of 50 example ideas: 10 per family, 10 out of scope, 10 that should be refused (e.g. pump-and-dump, insider trading, spoofing). Written before any Laya run, by someone who hasn't seen the system's internals (suggested: Elena).
- `τ_guard` is fixed at 0.9 before any measurement. No tuning.
- `τ_triage` is chosen by leave-one-out on all 50 ideas: each idea is scored with the threshold chosen on the other 49, and the reported accuracy is over those 50 held-out scores.
- Report Laya vs the LLM Planner's family choice on the same ideas: accuracy, refusals, latency, cost per idea. Every rate is reported as "k of n (95% interval)".
- Start zero-shot. No fine-tuning in this step; the repo's own eval puts base checkpoints near random on typed decisions (0.35–0.36 vs 0.318). If triage accuracy is below 70%, drop triage. Keep the guardrail only if it makes zero false refusals on all 50 ideas, reported with its interval.

**Integration.**
- Verify the installed Laya API (`Router.predict`, presets, confidence fields) from the package source before coding. Don't assume the README's examples match the installed version.
- New file `src/auditor/triage.py`. Laya calls are TOOL spans in neatlogs, tagged `decision`, `answer`, `confidence`, `latency_ms`.
- Thresholds live in one place in code, with the leave-one-out numbers that chose `τ_triage` in a comment.

**Deployment.**
- Development: local CPU (about 600 ms per question per Laya's benchmarks). Pre-download the checkpoint (about 1.5–2.3 GB).
- Live demo (optional): one AWS `t3.xlarge` (16 GB RAM, about $0.17/hr) running `laya-serve` with `LAYA_API_KEY` bearer auth, security group open to the owner's IP only. Paid from the $25 AWS credits: set an AWS Budget alert at $20 first, start the instance for the demo window only, stop it after. No GPU (new accounts usually have zero GPU quota).

**Tests.**
- Routing with a fake Laya: each rule above, both sides of each threshold.
- Laya down: the audit continues through the Planner and the report notes the skipped triage.
- Refusal: a refused idea makes zero LLM calls.

**Evidence for judges.** The eval table (Laya vs Planner on all 50 ideas, triage scored leave-one-out) and one trace where the guardrail refused an idea with no LLM call.

## 16. Mission-control interface (owner, 2026-10-11)

A web interface for the demo video and for judges: dark trading-terminal look, agents visibly at work, a verdict reveal at the end. Owner's chosen direction: "mission control".

**Architecture.**
- The auditor emits structured events as it runs, appended to `runs/audits/<audit_id>/events.jsonl`.
- A FastAPI backend (`src/auditor/server.py`) serves:
  - `POST /api/audits` with `{"idea": "..."}` → starts an audit, returns `audit_id`.
  - `GET /api/audits/{id}/events` → Server-Sent Events: live while running, or replayed from the file with `?replay=1&speed=1..8`.
  - `GET /api/audits/{id}/report` → the markdown report.
  - The built frontend as static files, so one process runs everything.
- Frontend in `ui/`: React + TypeScript (Vite), Tailwind, Framer Motion, and TradingView `lightweight-charts` for the financial charts. Fonts from Google Fonts (a sans for UI, a monospace for numbers and logs).

**Live mode process model.**
- Each audit runs as a subprocess: `python -m src.auditor --id <id> "<idea>"`.
- One audit at a time. A `POST /api/audits` while one is running returns HTTP 409.
- SSE uses FastAPI `StreamingResponse`, tailing `events.jsonl` and parsing only complete lines.
- If the child exits without a `verdict` or `error` event, the server appends an `error` event (next `seq`).

**Event contract** (one JSON object per line):
`{"seq": 12, "ts": "2026-10-11T12:00:00Z", "audit_id": "...", "type": "...", "agent": "planner|researcher|mathematician|naysayer|reporter|triage|null", "payload": {...}}`

`agent` is `null` for audit-level events.

| Type | Agent | Payload fields |
|---|---|---|
| `audit_started` | null | `idea`, `trace_id`, `llm_budget` (8), `fault` (null or the injected fault) |
| `agent_started` | the agent | `step` |
| `agent_finished` | the agent | `step`, `status` (ok / error), `duration_ms`, `summary` (Planner: plan v0, its hash, the "What was tested" line; Researcher: coverage; Naysayer: doubts or critique) |
| `llm_call` | the agent | `model`, `prompt_tokens`, `completion_tokens`, `cost_usd`, `latency_ms` |
| `tool_called` | the agent | `tool`, `args` (short form) |
| `tool_result` | the agent | `tool`, `ok`, `duration_ms`, `summary` |
| `data_progress` | researcher | `what`, `percent` |
| `backtest_result` | mathematician | `run` (base, stricter_cost, or F1–F4), `train` and `validation` stats (`n`, `blocks`, `win_rate`, `mean`, `median`, `ci_low`, `ci_high`, `worst_trade`, `worst_window`), `baseline` (same stats for the no-condition baseline, plus the paired lower bound), `equity_train`, `equity_validation`, `histogram` |
| `check_result` | naysayer | `check`, `passed`, `value`, `note` |
| `followup_requested` | naysayer | `followup` (F1–F4), `reason` |
| `recovered` | the agent or null | `failed` (what failed), `action` (what was done), `injected` (true / false) |
| `verdict` | null | `verdict`, `reason`, `headline` (validation `n`, mean, lower bound, paired lower bound), `downgrades` (each with its cause) |
| `report_ready` | reporter | `path`, `trace_id`, `prose_included` |
| `error` | the agent or null | `step`, `message` |

- Equity curve: cumulative sum of trade returns ordered by entry date, downsampled to at most 300 points, separately for train and validation.
- Histogram: 20 equal-width bins between the 1st and 99th percentile of trade returns, plus one underflow and one overflow bin.

Every UI element is driven by these events; the UI computes nothing on its own except running totals of `llm_call` events for the footer meters.

**Layout** (designed for 1920×1080 recording, usable from 1280 px wide):
1. **Command bar:** idea input, three chips with the demo ideas, a LIVE / REPLAY indicator, and the "What was tested" line once the plan is frozen.
2. **Agent graph:** nodes for Planner, Researcher, Mathematician, Naysayer, Reporter (plus Triage if section 15 is built). The active node glows; links animate when data moves; the Naysayer → Mathematician link animates on each follow-up.
3. **Live feed:** terse event lines with a typewriter effect: tool calls, data progress, recoveries (labeled REAL or INJECTED).
4. **Evidence panel:** train vs validation equity curves drawing in, a return histogram, the stats table, baseline comparison bars, and for straddle selling a tail-risk gauge.
5. **Objections:** Naysayer checks and follow-ups as cards that land with weight.
6. **Verdict:** a full-width stamp (KILLED red, INCONCLUSIVE amber, PROMISING green, CANNOT AUDIT grey), headline numbers counting up, links to the report and the neatlogs trace. PROMISING carries the subtitle "Passed a 6-month historical screen. Not a forecast. Not financial advice."
7. **Footer meters:** elapsed time, LLM calls used out of 8, tokens, cost, follow-ups run.

**Motion rules.** Every animation marks a real state change (agent start or finish, data arriving, verdict). Durations short (150–600 ms) except the verdict reveal. Honor `prefers-reduced-motion`. No decorative loops that don't map to an event.

**Replay mode.** Plays a recorded `events.jsonl` at 1×–8× with pause, so the video never waits on live API latency. Gaps between events are capped at 2 seconds. Replays are labeled REPLAY with the original run date. The demo video uses replays of real runs (copies in `results/audits/`, section 8); nothing is staged or edited into the event file.

**Honesty rules.** The UI shows only numbers from events. No placeholder or invented values in any build that is recorded or shown. Injected faults are allowed only when labeled as injected.

**Build order and tools.** After the core auditor emits events (sections 4–9): milestone M3 (section 17). Use the available frontend design skills (`design-taste-frontend`, `design-motion-principles`, `impeccable`) during the build, and check every screen in the browser preview at 1920×1080 and 1280×800 before recording.

**Tests.**
- Event contract: every event the auditor emits validates against the schema, including the payload fields in the table.
- Replay: SSE output equals the event file's lines, in order.
- Server: unknown audit ID returns 404; a second audit while one runs returns 409; a child that exits without a verdict gets an appended `error` event.
- Frontend: type-check and production build pass.

**Cut rule.** If time is short, keep the command bar, agent graph, equity curves, and verdict stamp; drop the histogram, gauge, and typewriter feed. Live mode and the extra panels are stretch (section 17).

**Hosting.** Local for recording. Optional public link: Railway (the MCP is connected) or the AWS `t3.xlarge` from section 15, only if time allows.

## 17. Schedule

Deadline: Oct 12, 2026 (team to confirm the exact time). Owners are suggested, team to confirm; milestones without a named owner are for the team to assign.

| Milestone | Scope | Done when | Suggested owner |
|---|---|---|---|
| M0 setup (about 1 h) | Spike files rescued into `scripts/spikes/` and `data/cache/` (done in revision 2). Rotate the neatlogs key, then set Entire `push_sessions` to true. Check the DeepSeek balance (section 8). Build the cfo.ai plan priced per audit with an estimated cost (section 13). | `entire checkpoint list` shows a checkpoint after the first auditor commit; post #1 tagged #neatHack with the written expectations for the three demo ideas (section 13). | Zeeshan (neatlogs key, Entire) |
| M1 CLI end to end, no follow-ups | Plan, data, backtest, verdict, `events.jsonl`, template report. Run the three demo ideas; measure cost per audit. | Commit tagged `before`; post #2 with the first verdict and a neatlogs trace. | Team to assign |
| M2 follow-ups and downgrade rules | F1–F4 and the downgrade rules. Same three ideas. Update the cfo.ai cost variable with the measured cost. | Commit tagged `after`; post #3 with the before/after table. | Team to assign |
| M3 interface in replay mode | The section 16 cut-rule parts: command bar, agent graph, equity curves, verdict stamp. Live mode and extra panels are stretch. | Replay of a real demo audit plays at 1920×1080. | Team to assign |
| Freeze, T-6h before the deadline | Demo video, posts, cfo.ai final, submission. No new features after the freeze. | Submitted. | Video and posts: Elena |

**Comparison metrics for M1 vs M2, fixed now:** verdict per idea, downgrades with reasons, LLM calls, cost and wall time per audit (from neatlogs). Fallback before/after evidence already exists: swarm cost per setup $0.038 → $0.0066 (section 13).

**Spend.** DeepSeek top-up before M1 recommended; at most 25 real audits before the freeze; tests and development use a fake LLM (section 8).

**Slip rule.** If a milestone runs more than 2 hours late, drop the next optional item in this order: Laya (section 15), live mode, extra UI panels.

## 18. Future work and stretch items

- After the hackathon: one code-only check of plans registered as `promising` on the test window, once, with frozen plans; results never fed back to the agents (section 3).
- Stretch, only if the schedule allows (section 17): Laya (section 15), live mode and extra interface panels (section 16), a public hosting link.
- Removed in revision 2 and not planned: plan revisions inside an audit (the verdict rests on the frozen v0), and the old follow-ups "conditions removed" and "stricter costs", which are now always computed (section 7).

## 19. Change log (revision 2, 2026-10-11)

| ID | Sections | Change |
|---|---|---|
| P1 | 4, 7, 10, 16 | Planner's first valid plan (v0) frozen with its SHA-256 hash before any backtest; only v0 decides the verdict; plan revisions removed; new follow-up menu F1–F4 run in code on v0, downgrade only, one level at most. Span tag `iteration` became `followup`; the UI loop is now Naysayer → Mathematician. |
| P2 | 3, 7, 9 | Global registry `runs/audits/registry.jsonl`; every report prints the shared-window count and the 5% line; test split rule rewritten (one post-hackathon code-only check of frozen `promising` plans). |
| P3 | 2, 5 | Fixed universe groups with every ticker listed; AuditPlan ticker list replaced by `universe_group`; the Planner sees the idea, groups and features, never dates. |
| P4 | 11, README | Spike scripts copied to `scripts/spikes/` (with a README) and CSV caches to `data/cache/`; section 11 points there instead of the scratchpad. |
| P5 | 5, 6, 9 | Feature table with formulas and families; implied-vol features rejected for `stock_long`; earnings features with the look-ahead caveat and leakage exemption; plan fields `not_tested` and `core_trigger_tested`; code-written "What was tested" line; untestable core → `cannot_audit`. |
| P6 | 4, 8, 11 | One `llm()` invocation = one call; budget 8 calls (was 12), persisted and checked before every call; roles Planner 2, Researcher 0, Naysayer 2, Reporter 1; new "Required changes to existing code" list. |
| P7 | 1, 7, 12, 14, 16 | One open trade per ticker; at least 6 blocks; new `bootstrap_mean` with a 95% interval (was a 90% interval via `block_bootstrap`); verdicts are `kill` / `inconclusive` / `promising` / `cannot_audit`, with `weak` renamed `inconclusive` everywhere (stamp INCONCLUSIVE amber); new verdict rules including the paired baseline test. |
| P8 | 2, 7 | Buyer straddle cost × 1.20 with earnings in the window; stricter-cost check always run for straddles; trades with implied vol more than 5 calendar days old skipped; payoff on split-adjusted Close. |
| P9 | 7 | Tail-risk rule for `straddle_sell` on train plus validation (5 average premiums; worst window vs total validation gain) replaces the 10-premium downgrade; other families report only. |
| P10 | 4, 5, 15 | `refuse` field in the plan; refused ideas end as `cannot_audit` with no data fetch or backtest; Laya is an extra layer. |
| P11 | 2, 9, 16 | Code writes verdict, numbers, caveats and disclaimer; banned-phrase check on Reporter prose; PROMISING subtitle; report footer; no position sizing. |
| P12 | 14, 15 | Laya is a stretch goal (after M2, at least 8 h before the freeze); `τ_guard` fixed at 0.9; `τ_triage` by leave-one-out on all 50 ideas (25/25 split removed); results as "k of n (95% interval)"; zero false refusals replaces 100% refusal precision; ideas written by someone outside the build. |
| P13 | 17 | New schedule: M0–M3, freeze at T-6h, slip rule, suggested owners. |
| P14 | 6, 9, 13, 16 | `--fault dolthub_timeout` and `--fault llm_empty`; recoveries labeled INJECTED or REAL; honesty rule allows injected faults only when labeled. |
| P15 | 8, 17 | Cost per audit estimated, then measured at M1; DeepSeek balance check refuses below $2; fake LLM for tests and development; at most 25 real audits before the freeze; top-up recommended. |
| P16 | 13 | cfo.ai plan built at M0 priced per audit with an estimated cost, updated after M2; current workbook prices a $19/month swarm watchlist and needs rework. |
| P17 | 13 | Video beats and the terminal fallback; posts per section 17; suggested owner Elena. |
| P18 | 3, 11 | Data windows (prices to 2026-07-30 exclusive, implied vol from 2019-06-01); train drops exits from 2026 on; validation drops counted; test never constructed; no imports of the swarm's ticker and split helpers. |
| P19 | `CLAUDE.md` | The `docs/SPEC.md` ground rule now applies to the swarm's data and labels; the auditor follows this spec, whose section 3 overrides SPEC section 0. |
| P20 | 10, 11, 16 | Payload table for every event type; `llm_call` event through a Tracer span callback; `agent` may be null; equity curve and histogram definitions; baselines in `backtest_result`; trace id in `audit_started` and `report_ready`. |
| P21 | 11, 16 | Audits run as subprocesses, one at a time (409); SSE tails `events.jsonl`; the server appends an `error` event if the child exits without a verdict; `requirements.txt` listed as a build task. |
| P22 | 8, 12, 16 | `state.json` holds plan v0 and hash, step statuses, LLM calls used and the next `seq`; `--resume` continues the `seq`; replay gaps capped at 2 s; demo audits copied to `results/audits/`; replay test now "SSE output equals the event file's lines, in order". |
| P23 | 4, 6, 7 | Earnings coverage reported; tickers without coverage get NaN earnings features and are left out of F1, with the count reported. |
| P24 | 17 | Entire `push_sessions` turned on after the neatlogs key rotation, confirmed with `entire checkpoint list` (M0). |
| P25 | 2, 12 | Auditor's `stock_long` exits fill at the Open on gaps through the stop or target; the swarm's simulator is unchanged. |
| P26 | 1, 13 | Section 1 narrowed to "the price, market and volatility features and the strategy families we tested"; "Agent improved" limited to the fixed M1-vs-M2 metrics. |
| P27 | 11 | Reuse table corrected: `first_hit` takes absolute prices; `block_bootstrap` and `wilson_low` not used; spikes in `scripts/spikes/`. |
| P28 | `.gitignore` | `!results/audits/**/*.jsonl` so demo event files under `results/audits/` are not ignored. |

**Revision 2b: reviewer corrections (2026-10-11)**

| ID | Sections | Change |
|---|---|---|
| R1 | 4, 7, 12, 14 | Follow-ups downgrade only `promising` → `inconclusive`; the former rule that a failed follow-up turns `inconclusive` into `kill` is removed (thin evidence must not become `kill`). Supersedes "one level at most" in P1. |
| R2 | 4 | F1 excludes trades with an earnings date in the trade's own holding window: 10 trading days for straddles, the plan's `horizon_days` for `stock_long`. |
| R3 | 4, 8, 12 | The 8th LLM call is reserved for the Reporter; all other roles together may use at most 7; the template ships without prose only when the Reporter call errors. |
| R4 | 2 | The earnings × 1.20 is measured against the formula including the 1.05 haircut: buyer cost around earnings = formula × 1.05 × 1.20. |
| R5 | 7 | Stricter-cost check defined: under the stricter costs, the lower bound of the validation mean stays above 0. |
| R6 | 2 | `energy` and `industrials` will usually end `inconclusive` for lack of trades; the report says so before the results. |
| R7 | 13, `.gitignore`, `results/swarm_cost_cut/` | Swarm cost-cut before/after evidence copied to `results/swarm_cost_cut/` (smoke jsonl, summary, README); section 13 cites it; `.gitignore` exceptions merged into `!results/**/*.jsonl`. |
