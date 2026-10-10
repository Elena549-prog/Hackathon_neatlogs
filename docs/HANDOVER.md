# Handover: Steps 1–4 status (2026-10-10)

Branch `step-1-4` holds everything below (the `baselines` branch is merged in). Draft PR: #1.
Read this first, then `docs/SPEC.md` (see its change log in section 0).

## Where things stand

| Step | Status |
|---|---|
| Setup | Done |
| 1. Laya schema check | Done. Format in `docs/laya_schema.md`. Zero-shot smoke test (`src/laya_smoke.py`) not run yet: needs Hugging Face access |
| 2. Price data | Done. 2023-10-01 to 2026-09-30 (first year = feature history only) |
| 3. Labels and splits | Done. Leakage test passes |
| 4a. Laya export | Done. 2,526 train rows |
| 4b. Fine-tune | Done on Kaggle (log below). Checkpoint is not in Git (see "The fine-tuned model") |
| Baselines (extra, outside SPEC) | Done. No model beats the base rate on validation |
| **Next: score Laya on validation** | **Script ready, not run.** See "What to do next" |

All 38 tests pass: `python -m pytest tests/ -q`.

## Decisions made (by Elena)

1. Price history starts 2023-10-01 so the 200-day average exists from the first train date. Split dates and the label rule are unchanged. Train grew from 455 to 1,263 setups.
2. Step 4b uses `src/finetune_laya.py` (`laya.train.finetune` on our JSONL, library defaults), not the Kaggle notebook named in SPEC 5b. That notebook trains on the public `LocalLLaMA/typed-decisions` dataset, not on an uploaded file.

## Still open for the owner

1. **High/Low scaling.** Entry is the adjusted close; Yahoo's High/Low are unadjusted. They are scaled by each day's Adj Close / Close so both sides match. Raw High/Low would change 132 of 2,185 train+validation setups. See `src/labels.py`, `adjusted_high_low`.
2. **`runs/` is gitignored** but SPEC section 6 lists `runs/*.md` as deliverables. Until decided, the key numbers are copied into this file.
3. **Calibration split.** `laya.train.finetune` fits temperatures on 10% of the train file, not on the validation split as PLAN Phase 3 says.
4. **Adding news text** as a new input, given that price features alone show no signal (below). Needs a historical, timestamped news source.

## Results so far

### Price data (Step 2)
All 5 tickers (AAPL, MSFT, GOOGL, AMZN, NVDA): 752 trading days, 2023-10-02 to 2026-09-30, no missing Adj Close, no duplicate dates, no gap over 5 trading days.

### Labels (Step 3)

| Split | Setups | Positives | Positive rate | Dates |
|---|---|---|---|---|
| train | 1,263 | 511 | 40.5% | 2024-10-01 to 2025-12-31 |
| validation | 577 | 211 | 36.6% | 2026-01-02 to 2026-06-30 |
| test | 231 | 94 | 40.7% | 2026-07-01 to 2026-09-15 (not used for anything else) |

379 setups dropped because neither +5% nor −3% was hit within 10 days.

### Baselines on validation (`src/baselines.py`)
Trained on train, scored on validation. Settings fixed in advance, not tuned on validation.

| Model | AUC (90% interval) | Brier skill vs base rate |
|---|---|---|
| Base rate (40.5%) | 0.500 | 0% |
| Logistic regression | 0.462 (0.36–0.56) | −11.7% |
| Random forest | 0.466 (0.41–0.54) | −5.9% |
| Gradient boosting | 0.497 (0.43–0.58) | −14.1% |

No model beats always predicting the base rate. The models do fit their training data (in-sample AUC up to 0.98), so this reads as "no generalizable signal in the 7 price features", not a bug. With the earlier 455-setup train set the picture was the same.

### Fine-tune log (Step 4b)

| Item | Value |
|---|---|
| Where | Kaggle notebook, GPU T4 (one GPU used, `cuda:0`), run by Elena |
| Date | 2026-10-10, afternoon (exact UTC start time not recorded) |
| Script | `laya.train.finetune` with `TrainConfig()` defaults, as in `src/finetune_laya.py` |
| Base model | `convaiinnovations/laya` (Hugging Face) |
| Data | `data/laya_train.jsonl`, 2,526 rows (1,263 train setups × 2 questions) |
| Items | 2,274 train, 252 calibration (10% held out by Laya), 0 skipped |
| Optimizer | 144 updates over 4 epochs, effective batch 64 (micro-batch 8 × grad-accum 8) |
| Runtime | 6.9 minutes |
| Epoch mean loss | 0.743, 0.612, 0.552, 0.436 |
| Fitted temperatures | choice 3.570, score 1.0 (unused), noul 1.770 |
| Warnings | PyTorch `lr_scheduler.step()` before `optimizer.step()` (harmless: fp16 grad scaler skipped the first step). No collapse warning reported |

Laya's own before/after table, on the 252 calibration items. **In-sample**: same period as training, overlapping 10-day windows, and the twin question of a setup may be in training. Not a held-out result.

| Metric | Before | After |
|---|---|---|
| Accuracy | 0.480 | 0.691 |
| Loss | 0.981 | 0.607 |
| ECE | 0.213 | 0.062 |
| Brier (top-1) | 0.317 | 0.209 |
| Mean confidence | 0.681 | 0.674 |

For scale: always answering "no/hold" is right about 60% of the time.

## The fine-tuned model

Not in Git (about 1.5 GB; `runs/` and `*.safetensors` are gitignored). It lives in Elena's Kaggle notebook output (`/kaggle/working/laya_finetuned`, plus `laya_finetuned.zip`). For a laptop run, put it here:

```
runs/checkpoints/laya_finetuned/
    model.safetensors, rl_agent_config.json, questions.json, train_report.json,
    encoder/, tokenizer/
```

`checkpoint_latest/` inside is a per-epoch backup of the same run and is not needed.

## What to do next: score Laya on validation

This is the result that answers "does Laya beat the baselines?". It needs internet access to Hugging Face (to load the zero-shot model for comparison) and is faster on a GPU.

### Route A (easiest): in Elena's Kaggle notebook

The fine-tune notebook and two private datasets (`laya-train`: training rows; `laya-validation`: `laya_validation.jsonl` + `score_laya.py`) are in Elena's Kaggle account.

1. Open the notebook. Check the session: GPU T4 on, Internet on.
2. Check that the model is still there: `!ls /kaggle/working/laya_finetuned`. The notebook uses "No persistence", so if the session ended, `/kaggle/working` is empty. Then re-run the install cell (`!pip install -q laya`) and the training cell (about 7 minutes).
3. Make sure `laya-validation` is added as an input, then run:

```python
import glob
data = glob.glob("/kaggle/input/**/laya_validation.jsonl", recursive=True)[0]
script = glob.glob("/kaggle/input/**/score_laya.py", recursive=True)[0]
!python {script} --data {data} --models convaiinnovations/laya /kaggle/working/laya_finetuned --out /kaggle/working/laya_validation_scores.json
```

4. Copy the printed table into the baseline table above and commit. To keep the model, use **Save Version → Save & Run All** so Kaggle stores the outputs permanently.

### Route B: on a laptop

From the repo root:

```bash
pip install pandas numpy yfinance pytest scikit-learn laya
python src/data.py                      # prices (needs Yahoo Finance access)
python src/labels.py                    # setups.csv
python src/export_laya.py --validation  # data/laya_validation.jsonl, 577 rows
python src/score_laya.py --models convaiinnovations/laya runs/checkpoints/laya_finetuned
```

`score_laya.py` prints AUC (with the same block-bootstrap interval as the baselines), Brier skill vs base rate, log loss and accuracy, for both questions (yes/no and buy/hold) and both models (zero-shot and fine-tuned). It refuses test-split rows. Add the rows to the baseline table above.

If the zip is not available, re-run the fine-tune instead (about 7 minutes on a Kaggle T4): `python src/finetune_laya.py`.

**Expectation, written down before the run:** fine-tuned Laya lands near AUC 0.5 on validation, like the baselines. A clear gain would be worth checking carefully (leakage, overlap) before believing it.

## Environment notes

- The cloud workspace used for this work could not reach Yahoo Finance or Hugging Face. Downloads and model runs happened on a laptop and on Kaggle.
- Kaggle needs phone verification for GPU and internet. Notebook outputs vanish when a "No persistence" session ends; use Save Version to keep them.
