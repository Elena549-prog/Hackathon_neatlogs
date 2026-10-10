# Trading Swarm + Laya: Step-by-Step Guide

Status: plan approved. No product code yet. Start at Step 0 on go.

Hard rules: paper trades only. No personal financial advice. Test window touched once.

## Frozen decisions

| Item | Value |
|---|---|
| Watchlist | 5 large-cap tickers (pick now, don't change) |
| Price history | 2024-10-01 to 2026-09-30, daily OHLCV |
| Train | 2024-10-01 to 2025-12-31 |
| Validation | 2026-01-01 to 2026-06-30 |
| Test | 2026-07-01 to 2026-09-15 (after LLM cutoff; 10 forward days resolvable) |
| Label | +5% hit before −3% within 10 trading days = 1; opposite first = 0; neither = drop |
| Minimum approved trades | 50 for significance; below that, report directional only |
| Naysayer rounds | max 2 |
| Laya go/no-go margin | fine-tuned must beat LLM-alone on validation precision by ≥3 points |

Verify the LLM knowledge cutoff in Step 0. If it is later than 2026-07-01, anonymize tickers and dates in prompts for the test run.

## Step 0: Setup (hour 0–1)
1. Create folders: `data/`, `src/`, `tests/`, `runs/`, `results/`, `docs/`.
2. Create a Python venv. Install: `pandas numpy yfinance anthropic laya`, plus the neatlogs SDK.
3. Verify the install names and steps for neatlogs, Entire, and cfo.ai from their docs. Don't assume.
4. Sign up at cfo.ai/neathacks. Cancel the subscription in Settings → Billing immediately.
5. Set API keys as environment variables. Never write them in files or chat.
- **Done when:** `python -c "import laya, pandas, anthropic"` runs without error, and `laya --help` prints usage.

## Step 1: Laya schema check (hour 1–2)
1. Read `laya/train.py` in the installed package. Record the exact JSONL fields and types in `docs/laya_schema.md`.
2. Run zero-shot Laya on 20 dummy rows. Record latency per question.
- **Done when:** one row round-trips through Laya and `docs/laya_schema.md` lists the exact fields.

## Step 2: Price data (hour 1–3)
1. `src/data.py`: download daily OHLCV for the 5 tickers, 2024-10-01 to 2026-09-30. Save to `data/prices/<TICKER>.csv`.
2. Check for gaps longer than 5 trading days. Check row counts per ticker.
- **Done when:** every ticker has full coverage, and the gap check passes or the ticker is replaced before Step 3.

## Step 3: Labels and splits (hour 3–6)
1. `src/labels.py`: for each setup, label 1 if +5% is hit before −3% within 10 trading days, 0 if −3% comes first, drop if neither.
2. Assign each labeled setup to train, validation, or test by its setup date.
3. Print positive rate per split.
- **Done when:** a test file checks the label rule on 3 hand-made price paths (one win, one loss, one neither). Positive rate is between 10% and 90% in each split. If not, stop and report before continuing.

## Step 4: Laya dataset and fine-tune (hour 6–7)
1. Export the **train split only** to JSONL in the schema from Step 1.
2. Upload the JSONL as a Kaggle dataset. Open `notebooks/laya_finetune_typed_decisions_2xT4_kaggle.ipynb` from the Laya repo and point it at our data.
3. Start the run. Record the start time in `runs/finetune_log.md`. Budget 5 hours.
- **Done when:** the job is running and the start time is logged. Keep working while it runs.

## Step 5: Swarm (hour 7–14)
Build four agents and two tools:
- **Researcher:** reads price features (returns, volatility, trend) from `src/data.py`. Every fact cites its source column.
- **Planner:** outputs a trade plan as JSON: ticker, direction, entry, stop, target, thesis in one sentence.
- **Mathematician:** code, not LLM. Computes expected value, position size, and max loss. Runs a simple backtest of the thesis on the train split.
- **Naysayer:** approves or blocks, and lists each objection. Max 2 rounds, then drop.
- **Tools:** `get_prices`, `backtest`.
- Trace every LLM and tool call with neatlogs from the start.
- **Done when:** one end-to-end run on one validation setup outputs a decision JSON, and its trace appears in neatlogs.

## Step 6: Baselines (hour 14–16)
Run on the validation split and save each to `runs/`:
1. LLM swarm alone (no Laya)
2. Random picks (seeded)
3. Buy-and-hold
- **Done when:** three result files exist with precision of approved trades and approved-trade count for each.

## Step 7: Laya zero-shot and checkpoints (hour 16–18)
1. Run zero-shot Laya on validation. Compare against the random reference of 0.318 from the Laya repo's own eval.
2. Entire: initialize the repo. Checkpoint the dataset hash, split dates, label rule, and the fine-tune config.
- **Done when:** zero-shot numbers are logged and the Entire checkpoint is visible.

## Step 8: cfo.ai draft (hour 18–20)
1. Build the model sheet: revenue tiers by watchlist size, cost per decision from neatlogs token counts × model price, Laya marginal cost near zero, runway, base and growth scenarios.
- **Done when:** the sheet computes cost per decision and runway from cell formulas, not typed values.

## Step 9: Go/no-go on Laya (hour 24–30)
1. Check the Kaggle job. When it finishes, load the checkpoint and run on validation.
2. **Pass** if fine-tuned Laya precision beats LLM-alone by ≥3 points on validation.
3. **Fail** → switch to fallback: drop Laya from the accuracy claim, keep the swarm, and say so in the submission. Don't spend more hours on Laya.
- **Done when:** a decision is recorded in `runs/decision.md`, with the numbers that justify it.

## Step 10: Ensemble tuning (hour 30–36)
1. Fit Laya temperatures on validation (not training).
2. Grid search: weight `w` in {0, 0.25, 0.5, 0.75, 1}, threshold `τ` in {0.5, 0.6, 0.7}. Choose on validation only.
3. Freeze the chosen `w` and `τ`.
- **Done when:** a single chosen config is saved to `results/frozen_config.json`.

## Step 11: Test evaluation (hour 36–40), once
1. Run the frozen config on the test split. Do not change anything after this.
2. Report: precision of approved trades, false-approve rate, calibration bins (≥10 per bin), and bootstrap confidence intervals (1000 resamples).
3. Compare against all baselines from Step 6.
- **Done when:** `results/test_report.md` exists. It states the approved-trade count, and whether results are significant or directional.

## Step 12: Demo and submission (hour 40–46)
1. neatlogs: screenshots of a trade trace, and the run comparison (LLM alone vs ensemble).
2. Demo video: problem, the swarm, the naysayer blocking a bad trade, the test result (good or bad), cfo.ai numbers, Entire checkpoint.
3. Entire: attach one real checkpointed change to the submission.
4. cfo.ai: export the final model sheet.
5. Write 2–3 build-in-public posts over the two days.
- **Done when:** video is uploaded, submission write-up links the test report, and the Entire checkpoint and cfo.ai export are attached.

## Step 13: Buffer (hour 46–48)
No new features. Fix only what breaks the demo.

## Cut list if behind
Cut in this order, last first:
1. Drop the mathematician's backtest. Keep EV and sizing.
2. Drop the naysayer's second round.
3. Cut the watchlist to 3 tickers.
4. Drop the Laya ensemble and report the fallback.

## Verification rules for every step
- Run the real thing and look at the output. "Should work" is not done.
- Log commands and outputs to `runs/` so the result can be checked later.
