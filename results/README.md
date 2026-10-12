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

## Test result (run once, 2026-10-12)

Files: `swarm_test_summary.md`, `swarm_test.jsonl` (231 lines, 0 errors). LLM cost $0.60.

| | Count |
|---|---|
| Setups | 231 |
| Skipped by the watcher (no LLM call) | 207 |
| Woken | 24 |
| Approved (paper trades) | **0** |
| Dropped: cautious hit rate at or below the 37.5% break-even | 19 |
| Dropped: fewer than 30 comparable past setups | 3 |
| Dropped: Naysayer LLM blocked | 2 (AMZN 2026-08-28 passed the gate by 1.05 points, label 0; AMZN 2026-07-30, label 1) |

**Reading.** The swarm made no trades on the test window. Unlike validation, this window had an edge for the fixed bet: approving every woken setup gives 41.7% precision (every setup: 40.7%), above the 37.5% break-even, about +0.3% per trade from the labels; buy-and-hold over the split was +9.6%. The gate's cautious lower bound was too strict to take that small edge, so on the test window the swarm was safe but not useful. Directional only (0 approvals, far below 50). Nothing was changed after this result.

## Current config on validation (run 2026-10-12, after the test run)

Files: `swarm_validation_current_summary.md`, `swarm_validation_current.jsonl`. Same frozen config as the test run, on the full validation split (it had only ever run there on 30 setups). LLM cost $2.87.

| | Validation | Test (above) |
|---|---|---|
| Woken by the watcher | 98 of 577 | 24 of 231 |
| Approved | 0 | 0 |
| Approve every woken setup: precision | 43.9% | 41.7% |
| Naysayer blocked a plan that passed the gate | 6 (3 label 1, 3 label 0) | 2 (1 label 1, 1 label 0) |

**Reading.** The swarm has approved one trade in all runs to date (old config, GOOGL 2026-05-29, −3%). The watcher alone (1.5 x 20-day vol, set on train for cost) selected setups above the 37.5% break-even in both windows, but neither sample is large enough to call that an edge (n 98 and 24). The gate plus the Naysayer declined all of them. Run after the test result, so it is evidence about the config, not a basis for changing it and re-testing on the same data.

## Naysayer v2: post-hoc replay of AMZN 2026-07-30 (demo, not evidence)

Naysayer v2 (`f5332a2`) leaves the evidence bar to the coded gate and blocks concrete defects only; the reason is the validation figure above (v1's blocks of gate-passing plans would have won 16 of 38). To isolate the prompt change, `scripts/naysayer_replay.py` gave v2 the exact plan, facts and math v1 saw for AMZN 2026-07-30 in the test run (input copied from its neatlogs trace into `posthoc_amzn_v1_naysayer.json`).

| | Verdict |
|---|---|
| v1 (test run) | block: "ret_1d > 0.01 does not express a strong one-day reversal" |
| v2 (replay) | approve, no objections |
| Paper trade | long at 235.50, stop 228.44, target 247.28: target hit on day 1 (next close 271.58), **+5.0%** |

Result in `posthoc_amzn_v1_naysayer_v2.json`. **Post-hoc:** this setup was in the test window already seen, and v2 was written after the test run, so this shows what the change does, not that it works. The overnight +15% gap was not predictable from the plan. A full re-run of the setup with v2 (`runs/swarm_test_posthoc_AMZN_2026-07-30.jsonl`) did not reach the Naysayer: the Planner wrote different plans (round 1 failed the gate with n 2, round 2 was invalid). Evidence for v2 can only come from new days (`src/forward.py`).

The replay was run twice more on 2026-10-12 (once filmed in a terminal, once with `--events` for mission control); v2 approved both times. The second wrote `audits/trade-amzn-2026-07-30/events.jsonl`, which the mission-control UI replays as a trade decision (chip "AMZN 2026-07-30 · swarm trade decision"). Same post-hoc caveat.

## Traces

Every setup is one neatlogs trace in the `trading-swarm` workflow: a WORKFLOW span `swarm`, with AGENT and TOOL spans (researcher, planner, mathematician, naysayer, get_prices, backtest) tagged `agent`, `round`, `ticker`, `date`, and neatlogs' own LLM spans nested under each agent.
