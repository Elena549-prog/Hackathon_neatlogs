# Spec: Four-agent swarm with tracing and paper-trade simulator

Status: draft for review. No code until approved. Covers step 4 of the approved plan (`GUIDE.md` step 5).

Depends on: `docs/SPEC.md` steps 1–3 (price data, `src/features.py`, `src/labels.py`, `data/labels/setups.csv`).

## 1. Goal

For each trade request, four agents decide whether to paper-trade a setup. The swarm's verdict and the paper trade outcome are logged so later steps can measure accuracy. This step does not add Laya. Laya joins in step 8 (ensemble).

## 2. Scope

In scope:
- Watcher that turns a setup into a trade request.
- Researcher, Planner, Mathematician, Naysayer agents.
- Two tools: `get_prices` and `backtest`.
- Naysayer debate loop, max 2 rounds.
- Paper-trade simulator.
- neatlogs tracing on every LLM and tool call.
- Decision log written to `runs/`.

Out of scope:
- Laya (step 8).
- Live data, live trading, real orders.
- News or text sources. Inputs are price features only.
- Entire and cfo.ai (separate steps).

## 3. Models

| Agent | Model | Why |
|---|---|---|
| Researcher | `claude-haiku-5-5` | Cheap. Summarizes features with citations. |
| Planner | `claude-sonnet-5-5` | Needs judgment to form a plan. |
| Naysayer | `claude-sonnet-5-5` | Needs judgment to find flaws. |
| Mathematician | none (code) | Sizing and EV are arithmetic. Don't ask an LLM. |

Model IDs come from the environment list. Confirm before first run.

## 4. Data flow

```
setup (ticker, date) from data/labels/setups.csv
  → Researcher: features + cited facts
  → Planner: trade plan (JSON)
  → Mathematician: EV, size, max loss, backtest on train split
  → Naysayer: approve | block (+ objections)
      block and round < 2 → Planner revises with objections → Mathematician → Naysayer
      block and round = 2 → dropped
  → approve → paper trade recorded
```

Each setup gets at most two rounds. A dropped setup is logged as `dropped`, not as a loss.

## 5. Schemas

**Setup input** (one row from `data/labels/setups.csv`):
`ticker, date, split, label, <feature columns>`. The label is used only for scoring, never passed to agents.

**Trade plan** (Planner output, JSON, validated):
```json
{
  "ticker": "AAPL",
  "direction": "long",
  "entry": 189.50,
  "stop": 183.82,
  "target": 198.98,
  "horizon_days": 10,
  "thesis": "one sentence",
  "conditions": {"ret_20d": [">", 0.03], "vol_20d": ["<", 0.02]},
  "facts_cited": ["ret_20d", "vol_20d"]
}
```
Rules: `direction` is `long` only (no shorts in this step). `facts_cited` must be a subset of the researcher's output keys.

**Fixed levels.** The Planner decides only *whether* to trade and *why* (`thesis`, `conditions`). The levels follow the label rule in `docs/SPEC.md` section 0, so every component scores the same bet:
- `entry` = Adj Close on the setup date
- `stop` = `entry` × 0.97
- `target` = `entry` × 1.05
- `horizon_days` = 10

The validator rejects any plan whose levels differ from these by more than 0.01. Reason: labels, Laya and the train-split backtest all answer "+5% before −3% within 10 days". If the Planner chose other levels, the swarm and Laya would judge different bets and the ensemble (step 8) could not combine them fairly.

**Conditions.** `conditions` states the thesis as checks on the setup's own feature values, e.g. "20-day return above 3% and 20-day volatility below 2%". Allowed operators: `>`, `<`, `>=`, `<=`. Keys must be feature columns from `data/labels/setups.csv`. The setup being decided must satisfy its own conditions. The backtest uses them to find comparable past setups (section 6).

**Naysayer output** (JSON):
```json
{"verdict": "approve" | "block", "objections": ["..."]}
```
Block requires at least one objection. Approve with objections is not allowed.

**Decision log** (one line per setup in `runs/swarm_<split>.jsonl`):
`ticker, date, split, rounds, verdict, plan, objections, trade_outcome, pnl_pct`

## 6. Tools

- `get_prices(ticker, end_date, lookback_days)`: returns Adj Close and High/Low up to `end_date` only. Must never return data after `end_date`. This is the leakage guard for the agents.
- `backtest(plan, split="train")`: finds the train-split setups that satisfy `plan.conditions` and returns, under the same label rule:
  - `n`: number of matching setups,
  - `hit_rate`: share of them labelled 1,
  - `hit_rate_low`: the lower end of the 95% Wilson interval for that share.

  Train split only. Matching setups from dates on or after the setup being decided are excluded, so a validation run never sees later data.

## 7. Position sizing (Mathematician)

- Paper account starts at 100,000 (simulated currency).
- Risk per trade: 2% of account. Size = risk ÷ (entry − stop).
- EV = p × (target − entry) − (1 − p) × (entry − stop), with **p = `hit_rate_low`** from the backtest, not the plain hit rate. With the fixed +5% / −3% levels, EV > 0 exactly when p > 3 / 8 = 37.5%.
- **Hard gate:** the Naysayer must block if `n` < 30 (too little evidence) or EV ≤ 0. The Mathematician reports `n`, `hit_rate`, `hit_rate_low` and EV.
- Why the cautious estimate: the overall train hit rate is 40.5% (1,263 setups), already above the 37.5% break-even. Using the plain rate, almost any plan would show a positive EV and the gate would rarely fire. Step 1–4 baselines also found no reliable signal in the price features (validation AUC 0.46–0.50), so a gate that demands evidence is the honest default. Examples with the 95% Wilson lower bound:

  | Matching setups | Hit rate | Lower bound | Gate |
  |---|---|---|---|
  | 40 | 45% | 30.7% | block |
  | 300 | 45% | 39.5% | pass |
  | 1,263 (all train) | 40.5% | 37.8% | pass, barely |

- Step 8 (ensemble): once Laya is available, its calibrated probability can replace `hit_rate_low` as p. Decide then; out of scope here.
- No fees or slippage in this step. State that in the report.

## 8. Paper-trade simulator

- Approved plans open a simulated position at `entry`.
- The position closes on the first of: target hit, stop hit, or horizon expiry. Use the same High/Low rule as the labels.
- `trade_outcome` = `win` | `loss` | `expired`. `pnl_pct` = realized return.
- Simulator reads future prices only after the decision is logged. Decisions never see the outcome.

## 9. Tracing (neatlogs)

- Wrap each LLM call and tool call in a neatlogs span. Tag spans with `agent`, `round`, `ticker`, `date`.
- Record: inputs, outputs, latency, tokens, cost.
- Verify the neatlogs SDK install and API in its docs first. If the API differs from what's assumed here, stop and report.

## 10. Files

```
src/agents/researcher.py
src/agents/planner.py
src/agents/mathematician.py
src/agents/naysayer.py
src/swarm.py          # loop, rounds, decision log
src/tools.py          # get_prices, backtest
src/simulator.py      # paper trades
src/tracing.py        # neatlogs wrapper
tests/test_tools.py
tests/test_swarm.py
tests/test_simulator.py
```

## 11. Tests (must pass before any run on real setups)

- `get_prices` returns nothing after `end_date`. Test with a series that has a spike after the date.
- Plan validator rejects: `direction` = short, `facts_cited` not in researcher output, `stop` ≠ `entry` × 0.97, `target` ≠ `entry` × 1.05, `horizon_days` ≠ 10, `entry` ≠ the setup's Adj Close, `conditions` with an unknown feature or operator, and conditions the setup itself does not satisfy.
- Backtest: on a hand-built table, `n`, `hit_rate` and `hit_rate_low` match hand values (e.g. 18 of 40 → 45.0%, lower bound 30.7%). Setups dated on or after the decision date are never counted.
- Gate: `n` = 29 blocks; `hit_rate_low` = 0.374 blocks; `hit_rate_low` = 0.376 with `n` ≥ 30 passes.
- Naysayer `approve` with objections is rejected. `block` with no objections is rejected.
- Round cap: a naysayer that always blocks drops the setup after 2 rounds.
- Simulator: a stop-first path closes as `loss`. A target-first path closes as `win`. Same-day both hit closes as `loss`.
- Mathematician: EV formula matches a hand example.
- Tracing: a run writes spans with `agent`, `round`, `ticker`, `date` tags.

## 12. Run plan

1. Smoke run: 5 setups from the validation split, end to end. Check the log has one line per setup.
2. Baseline run on the validation split: LLM swarm alone. Save to `runs/swarm_validation.jsonl`.
3. Random baseline and buy-and-hold on the same setups (seeded), saved to `runs/`.
4. Do not run on the test split in this step.

## 13. Acceptance

- All tests in section 11 pass.
- Smoke run log has the expected number of lines and valid JSON on each line.
- Baseline summary: approved count, precision of approved trades, and dropped count. Saved to `runs/swarm_summary.md`.

## 14. Decisions to confirm

1. Model IDs in section 3 (Sonnet for judgment, Haiku for research).
2. Max 2 naysayer rounds.
3. Long-only.
4. No fees or slippage in this step.
5. 2% risk per trade on a 100,000 paper account.
6. Fixed levels: stop −3%, target +5%, 10-day horizon, matching the label rule (section 5).
7. EV gate on the cautious hit rate: 95% Wilson lower bound, minimum 30 matching setups (section 7).
