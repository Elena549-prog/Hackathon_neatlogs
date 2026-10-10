# Plan: Paper-trading swarm with Laya accuracy layer

Status: approved. Step-by-step execution is in `GUIDE.md`.

## Goal
A price watcher triggers trade requests. A four-agent swarm (Researcher, Planner, Mathematician, Naysayer) decides. Laya improves decision accuracy. Everything runs as paper trades on historical replay. Success means a measured accuracy gain over baselines, not a profit claim.

## Decisions
- Historical replay, not live. Reproducible.
- Soft ensemble, not a hard gate. Accuracy is the goal.
- Fixed watchlist of about 5 large-cap stocks.
- Paper trading only. No personal financial advice.

## Phases

### Phase 0: Gate
- Read `laya.train` and confirm our labeled-data JSONL schema.
- Measure zero-shot Laya on our labels. Zero-shot scored near random in the repo's own eval (0.36 vs 0.318), so expect a weak baseline.
- Go/no-go: continue to fine-tuning only if the data format works. Otherwise go to the fallback.

### Phase 1: Data and labels
- Pick a free price-history source and confirm it covers the full window.
- Label rule, fixed before looking at results: a setup is positive if price hits +X% before −Y% within N trading days. Example: +5% / −3% / 10 days.
- Time splits:
  - Train: up to date T1
  - Validation: T1 to T2, used to tune threshold and weights
  - Test: after T2, touched once
- Leakage guard: the test window falls after the LLM's knowledge cutoff. If not possible, anonymize tickers and dates in prompts and say so in the demo.

### Phase 2: Swarm and tracing
- Build the four agents with neatlogs tracing on every LLM and tool call.
- Each run logs the verdict, Laya probability (once available), and the label outcome.

### Phase 3: Laya fine-tune
- Fine-tune `noul` (hits target before stop) and `choice` (buy/hold/sell) on the train split.
- Run on Kaggle 2×T4 (about 4–5 hours) or local MPS. Budget the time before starting.
- Calibration: fit temperatures on the validation split, not training items.
- Exclude `act_probability`. Its AUROC was 0.30 in the repo's eval, below random.

### Phase 4: Ensemble
- `score = w × LLM_verdict + (1 − w) × Laya_probability`
- Abstain when Laya confidence is below τ, and let the LLM decide alone.
- Tune w and τ on validation only. Report the chosen values.

### Phase 5: Evaluation (test set, once)
- Primary metric: precision of approved trades (share that hit target).
- Secondary: false-approve rate, and calibration bins with a minimum sample count per bin.
- Baselines on the same window: LLM swarm alone, Laya alone, random picks, buy-and-hold.
- Significance: bootstrap confidence intervals. Minimum approved-trade count is 50. Below that, results are directional only.

### Phase 6: Tool deliverables
- neatlogs: traces for every run. Accuracy by run, ticker, and confidence bucket. Calibration plot.
- Entire: checkpoints for dataset version, split dates, label rule, fine-tune config, and each threshold change.
- cfo.ai: model sheet with revenue tiers by watchlist size, cost per decision from neatlogs, Laya marginal cost near zero, runway, and base/growth scenarios.

## Fallback
If fine-tuning fails, or Laya doesn't beat LLM-alone on validation by a set margin (3 points), drop Laya from the accuracy claim. Keep the swarm and say so in the submission.

## Risks
| Risk | Mitigation |
|---|---|
| Fine-tune takes too long | Start early. Fallback decision at hour 30. |
| Too few trades for significance | Longer history, more tickers within the watchlist. Report as directional if still short. |
| LLM leakage | Post-cutoff test window, or anonymize prompts. |
| Data source unavailable | Choose and verify before Phase 1. |
| Laya schema mismatch | Phase 0 check. |

## Timeline (48 hours)
- Day 1 (0–24h): setup, data, labels, Kaggle fine-tune start, swarm, baselines, Entire, cfo.ai draft.
- Day 2 (24–48h): fine-tune go/no-go at hour 30, ensemble tuning, one-shot test, demo and submission, buffer.
