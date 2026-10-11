# Spec: Data, labels, and Laya fine-tune (Steps 1–4)

Scope of this spec: Steps 1–4 of `GUIDE.md`. Everything else in the project (swarm, ensemble, test evaluation, demo) is out of scope here.

Who runs this: a teammate working with Claude Code in this repo. No prior context from the project owner is assumed. Follow this spec exactly. If something is ambiguous, stop and report instead of guessing.

## 0. Frozen decisions (do not change)

| Item | Value |
|---|---|
| Tickers | AAPL, MSFT, GOOGL, AMZN, NVDA |
| Price history | 2023-10-01 to 2026-09-30, daily (the year before 2024-10-01 is feature history only; see change log) |
| Price field | Adjusted close for returns and features. High and Low for label hit checks |
| Entry price | Adjusted close on setup day t |
| Train split | Setup dates 2024-10-01 to 2025-12-31 |
| Validation split | Setup dates 2026-01-01 to 2026-06-30 |
| Test split | Setup dates 2026-07-01 to 2026-09-15 |
| Label | Within the next 10 trading days (days t+1 to t+10): if High ≥ entry × 1.05 before Low ≤ entry × 0.97, label = 1. If Low ≤ entry × 0.97 first, label = 0. If both happen on the same day, label = 0 (conservative). If neither, drop the setup |
| Setup set | Every trading day t in each split where t+10 exists in the data |
| Minimum positive rate per split | 10% and 90% |

**Test-split labels are produced only for the positive-rate check in Step 3. Do not train on them, tune on them, or look at Laya results on them.**

### Change log
- 2026-10-10 (decided by Elena): price history now starts 2023-10-01 instead of 2024-10-01. Reason: the 200-day moving-average feature needs 200 days of history, so with the old start the first ~200 days of every ticker were dropped and the train split kept only 455 setups (Jul–Dec 2025). The extra year is used only to compute features; setups are still made only for the split dates above, and labels are unchanged.
- 2026-10-10 (decided by Elena): Step 4b uses `src/finetune_laya.py` (`laya.train.finetune` on our JSONL, library defaults) instead of the Kaggle notebook, which trains on the public typed-decisions dataset rather than an uploaded file.

## 1. Repo setup (prerequisite)

1. Clone the repo. Work on a branch named `step-1-4` (do not commit to `main` directly).
2. Create folders: `data/prices/`, `data/labels/`, `src/`, `tests/`, `runs/`, `docs/`.
3. Add `.gitignore` with: `data/`, `runs/`, `*.pt`, `*.safetensors`, `*.onnx`, `.venv/`, `__pycache__/`, `.env`, `*.jsonl`.
4. Create a virtualenv. Python 3.10 or newer.
5. Install: `pip install pandas numpy yfinance laya pytest`.
6. Verify: `python -c "import laya, pandas, yfinance"` runs without error.

**Done when:** the imports work and `.gitignore` is committed.

## 2. Step 1: Laya schema check

**Goal:** know the exact input format Laya needs for fine-tuning, before writing any data code.

1. Find the installed package: `python -c "import laya, os; print(os.path.dirname(laya.__file__))"`.
2. Read `laya/train.py` (and any schema or dataset helper it imports). Record in `docs/laya_schema.md`:
   - Exact field names for one training row, including types.
   - How `state` and `questions` are encoded (JSON string or object).
   - The allowed `gold` value per task type: `noul`, `choice`, `score`.
   - Any required keys for `choice` (option labels) and for `noul` (yes/no encoding).
3. Run the zero-shot check on 20 dummy rows built from the schema. Record latency per question in `runs/zero_shot_smoke.md`.
4. If Laya does not expose a fine-tuning data loader, stop and report. Do not invent a format.

**Done when:**
- `docs/laya_schema.md` lists every required field with its type and an example row.
- One dummy row runs through Laya and returns a result.

**Stop and report if:** the schema differs from what this spec assumes in Step 4, or fine-tuning is not supported in the installed version.

## 3. Step 2: Price data

**Goal:** full daily price history for the 5 tickers.

1. Write `src/data.py` with a function `download_prices(ticker, start, end)` that returns a DataFrame indexed by date with columns: `Open, High, Low, Close, Adj Close, Volume`.
   - Use `yfinance.download(..., auto_adjust=False)`. Keep both `Close` and `Adj Close`.
   - Use `start=2023-10-01`, `end=2026-10-01` (end is exclusive). See the change log in section 0.
2. Save each ticker to `data/prices/<TICKER>.csv`.
3. Check each file:
   - Row count is roughly 500 per year of trading days. A small shortfall at the edges is fine.
   - No missing `Adj Close` values.
   - No gap longer than 5 consecutive trading days.
   - No duplicate dates.
4. Write `tests/test_data.py` with at least one check per rule above.
5. Save a summary to `runs/price_data_check.md`: row count, first and last date, and any gaps per ticker.

**Done when:**
- All 5 CSVs exist and pass the checks.
- `pytest tests/test_data.py` passes.

**Stop and report if:** a ticker fails the gap or missing-value check. Do not silently replace tickers. Report which ticker failed and why.

## 4. Step 3: Labels and time splits

**Goal:** a labeled setup table for each split. Labels depend only on future prices, and features depend only on past and current prices.

1. Write `src/labels.py` with:
   - `make_setups(prices_df) -> DataFrame` with one row per trading day t where t+10 exists. Columns: `ticker`, `date`.
   - `label_setup(prices_df, t_index) -> int | None`: applies the rule in section 0. Returns `None` for dropped setups.
2. Write `src/features.py` with `features_at(prices_df, t_index) -> dict` using only rows at or before t:
   - Returns over 1, 5, 10, and 20 trading days (from Adj Close).
   - 20-day volatility of daily returns.
   - Ratio of Adj Close to its 50-day moving average.
   - Ratio of Adj Close to its 200-day moving average. Use `NaN` if fewer than 200 days exist, and drop those setups.
3. Assign each setup to a split by its date using the boundaries in section 0.
4. Write `tests/test_labels.py` with at least these cases:
   - Win path: price rises 5% before falling 3%. Label = 1.
   - Loss path: price falls 3% first. Label = 0.
   - Same-day both hit. Label = 0.
   - Neither hit within 10 days. Setup dropped.
   - Near-end setup where t+10 does not exist. Not in the setup table.
   - **Leakage test:** `features_at` on the full series equals `features_at` on the series truncated at t. If not, fix the feature code. Do not change the test.
5. Write `data/labels/setups.csv` with columns: `ticker, date, split, label, features...`. Drop rows with `label` missing.
6. Print positive rate per split and per ticker. Save to `runs/label_summary.md`.

**Done when:**
- `pytest tests/test_labels.py` passes, including the leakage test.
- Positive rate is between 10% and 90% for each split.
- `runs/label_summary.md` lists counts and positive rates.

**Stop and report if:** any positive rate is outside 10–90%, or the leakage test fails. Do not adjust thresholds to fix the rate.

## 5. Step 4: Laya dataset export and Kaggle fine-tune

**Goal:** a Laya fine-tune on the train split only, started early, with the job logged.

### 5a. Export (train split only)

1. Write `src/export_laya.py` that reads `data/labels/setups.csv`, keeps `split == "train"` only, and writes `data/laya_train.jsonl`.
2. Map each setup to rows in the schema from `docs/laya_schema.md`. Use these questions unless the schema requires a different form:
   - `noul` row: `state` = features as a JSON object. `questions` = `["Will the price hit +5% before −3% within 10 trading days?"]`. `gold` = `label` (1 or 0).
   - `choice` row: `state` = same features. `questions` = `["Action: buy or hold?"]` with options `buy` and `hold`. `gold` = `buy` if label is 1, else `hold`.
   - Do not create `score` rows in this step.
3. If the schema in `docs/laya_schema.md` differs from this mapping, follow the schema. Keep the labels the same. Note the change in `docs/laya_schema.md`.
4. Check the output: row count equals the train setup count times the number of questions per setup. Print 3 random rows and check them by hand against the label rule.
5. Write `tests/test_export.py` to check that no row has a date after 2025-12-31.

**Done when:**
- `data/laya_train.jsonl` exists and contains train rows only.
- `pytest tests/test_export.py` passes.

### 5b. Kaggle fine-tune

1. The teammate needs a Kaggle account with GPU access (phone verification may be required). Do not commit any Kaggle token.
2. Upload `data/laya_train.jsonl` as a private Kaggle dataset.
3. Open `notebooks/laya_finetune_typed_decisions_2xT4_kaggle.ipynb` from the Laya repo (https://github.com/NandhaKishorM/laya). Copy it into Kaggle.
4. In the notebook settings: accelerator = GPU T4 ×2. Enable internet if the notebook downloads checkpoints.
5. Point the notebook at the uploaded dataset. Do not change epochs or batch settings for this first run. Defaults are 4 epochs, micro-batch 2, grad-accum 16.
6. Start the run. Record in `runs/finetune_log.md`: UTC start time, notebook version, dataset version, and the Kaggle session URL.
7. Expected runtime is 4–5 hours. Check the run every hour and log progress.
8. When the run finishes, download the checkpoint output and place it in `runs/checkpoints/` (gitignored). Record the file size and path in `runs/finetune_log.md`.

**Done when:**
- The run is started and logged.
- The checkpoint is downloaded and its path is logged, or the run failed and the failure is logged with the error text.

**Stop and report if:** the run fails, the dataset is rejected, or the run exceeds 6 hours. Do not restart with different settings without reporting first.

## 6. Deliverables and commits

Commit after each step, with a message naming the step, e.g. `Step 2: price data for 5 tickers`.

Required files at the end:
- `docs/laya_schema.md`
- `src/data.py`, `src/labels.py`, `src/features.py`, `src/export_laya.py`
- `tests/` with all test files passing
- `runs/price_data_check.md`, `runs/label_summary.md`, `runs/finetune_log.md`
- `data/` is not committed (gitignored)

Final report to the project owner: what was done, the test output, the label summary table, the Kaggle run status, and anything the owner must decide.

## 7. Rules for the teammate's Claude

- Follow this spec. Do not change frozen values in section 0.
- Never look at Laya results or labels on the test split.
- Never commit secrets: Kaggle tokens, API keys, `.env`. If one appears in a file, remove it and report.
- Never force-push or rewrite history.
- If a step is blocked, stop and report it. Do not work around it silently.
- Any step not listed here (swarm, ensemble, cfo.ai, neatlogs, Entire) is out of scope. Do not start it.
