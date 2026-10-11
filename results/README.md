# Results: swarm on the validation split (step 5)

Run on 2026-10-10 by the project owner, code at commit `49e074a` on branch `swarm`.

| File | What it is |
|---|---|
| `swarm_validation_summary.md` | The summary table written by `src/swarm.py` |
| `swarm_validation.jsonl` | One decision per validation setup (577 lines): verdict, rounds, final plan, objections, trade outcome, label |

## How it was run

```bash
python -m src.swarm --split validation --workers 16                 # first pass, stopped at 329 setups
python -m src.swarm --split validation --workers 8 --resume         # finished the rest
```

- Provider: DeepSeek. Researcher `deepseek-flash` (thinking off); Planner and Naysayer `deepseek-v4-pro` (thinking on, effort high). See `docs/SWARM_SPEC.md` section 3.
- Agents saw anonymized, normalized data only: no ticker, no date, prices scaled to 100.
- The first pass was stopped because DeepSeek returned 429 errors once the account balance ran low (its concurrency limit drops with the balance). `--resume` kept the 267 finished setups and re-decided the 62 errors and the 248 setups not yet reached. The final file has 0 errors and each setup exactly once.
- The test split was not used.

## Result

| | Count |
|---|---|
| Approved | 1 (0.2%) |
| Dropped: cautious hit rate at or below the 37.5% break-even | 329 |
| Dropped: fewer than 30 comparable past setups | 196 |
| Dropped: invalid plan after 2 rounds | 26 |
| Dropped: Naysayer LLM blocked a plan that passed the gate | 25 |

The one approved trade (GOOGL, 2026-05-29, "pullback inside an uptrend") lost 3%.

**Reading.** The swarm almost never traded. That is consistent with the data: approving every setup gives 36.6% precision, below the 37.5% break-even for the +5%/−3% bet, and the step 1–4 baselines found no signal in these price features (validation AUC 0.46–0.50). The result supports "the gate refuses a market with no edge", not "the swarm picks winners". One approval is not enough to say anything about precision.

## Cost

$11.76 logged for the resumed pass (upper bound: DeepSeek peak, cache-miss prices). The first pass was stopped before it wrote its cost; at the smoke-run rate (about $0.034 per setup) it was roughly $9. Exact spend is in the DeepSeek dashboard.

## Frozen config for the one test run (written 2026-10-12, before the run)

The test split (231 setups, 2026-07-01 to 2026-09-15, after the LLM cutoff) is run exactly once with this config; nothing changes after the result is seen.

- **Swarm alone.** Laya was never scored on validation (the checkpoint lives only in Elena's Kaggle notebook), so the plan's fallback applies: Laya is not part of the accuracy claim.
- Code: commit `45c5386` (branch `claude/demo-694260`). This is **not** the config of the validation run above: the price watcher (wake only on a 1-day move of at least 1.5 x 20-day vol) and "round 2 only for fixable failures" were added later for cost (`swarm_cost_cut/README.md`). The current config was never run on the full validation split.
- Gate unchanged: at least 30 comparable past setups; cautious (95% Wilson lower bound) hit rate above the 37.5% break-even; Naysayer LLM may still block. Max 2 rounds.
- Bet unchanged: long, +5% target before −3% stop within 10 trading days; no fees or slippage. Approved plans are paper trades closed by the simulator after the decision is logged.
- Models: Researcher `deepseek-flash`, Planner and Naysayer `deepseek-v4-pro` (`src/llm.py`).
- Agents see no ticker, no date, prices scaled to 100.
- Expected: few or no approvals (the watcher wakes 24 of 231 setups; validation approved 1 of 577). Fewer than 50 approvals means directional only.

```bash
.venv/Scripts/python.exe -m src.swarm --split test --final-test --workers 8
```

## Traces

Every setup is one neatlogs trace in the `trading-swarm` workflow: a WORKFLOW span `swarm`, with AGENT and TOOL spans (researcher, planner, mathematician, naysayer, get_prices, backtest) tagged `agent`, `round`, `ticker`, `date`, and neatlogs' own LLM spans nested under each agent.
