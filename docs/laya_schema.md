# Laya fine-tuning schema (Step 1)

Source: installed package `laya` 0.4.2, read from `laya/train.py` (`finetune`, `read_jsonl`, `items_from_rows`, `target_from_gold`, `target_from_expected`), `laya/agent.py` (`Agent._check_question`, `Agent._to_internal`) and `laya/common.py` (`serialize_state`, `QTYPES`).

**Fine-tuning is supported.** `laya.train.finetune(data, model_dir, output_dir, config)` takes a JSONL file (or a CSV) and has a built-in loader. A `dry_run(data, model_dir)` function checks a file without training.

## One training row

A JSONL file with one JSON object per line. Blank lines and lines starting with `#` are skipped.

| Field | Type | Required | Meaning |
|---|---|---|---|
| `state` | JSON object, list, or string | yes | The input the model reads. An object is turned into text with `json.dumps(state, ensure_ascii=False)`. A missing or empty state skips the row. |
| `questions` | JSON **object** (dict) | yes | Maps a question id (string) to a question definition. Not a list. |
| `gold` | JSON object (dict) | one of `gold` / `expected` | Maps a question id to `{"probabilities": {option_key: number}}`. |
| `expected` | JSON object (dict) | one of `gold` / `expected` | Maps a question id to a single answer value. Simpler alternative to `gold`. |

A question id that has no `gold` and no `expected` entry is ignored for that row (not counted as an error).

## `state` encoding

`state` is a real JSON object inside the row, not a JSON string. Laya serializes it itself. A string is also accepted and used as-is.

## `questions` encoding

A JSON object, keyed by question id. Each definition:

| Key | Type | Required | Notes |
|---|---|---|---|
| `type` | string | yes | `"noul"`, `"choice"` or `"score"` |
| `instructions` | string (or dict/list/number) | yes | The question text. Must not be empty. |
| `criteria` | depends on type | choice, score: yes. noul: no | See below |
| `labels` | dict `{"false": str, "true": str}` | no, noul only | Changes how the answer is worded. Not needed. |
| `option_order` | list of ints | no | Ignored in training (training draws its own order). |

### `noul` (yes/no)
- `criteria`: omit it, or a dict keyed only `"true"` / `"false"` with descriptions. Any other key is rejected.
- Options are always ordered `[false, true]`.
- `gold`: `{"probabilities": {"true": p, "false": 1 - p}}`. A missing key defaults to 0.5.
- `expected`: `true` / `false`, `1` / `0`, or the strings `"true"`, `"false"`, `"yes"`, `"no"`, `"1"`, `"0"`.

### `choice` (pick one option)
- `criteria`: a list of labels (`["buy", "hold"]`) or a dict `{label: description}`. Labels must be unique scalars (string, number, bool), not null.
- `gold`: `{"probabilities": {label: p, ...}}`, keyed by the label. A missing label counts as 0.
- `expected`: the label itself, e.g. `"buy"`.

### `score` (ordered levels, not used in Steps 1–4)
- `criteria`: a list of level descriptions, index 0 first.
- `gold`: `{"probabilities": {"0": p0, "1": p1, ...}}`, keyed by level index as a string.
- `expected`: a level index (an int, or a float between two levels for a split target) or a level string.

Probabilities are normalized to sum to 1. Negative or non-finite values raise an error. All-zero becomes uniform.

## Example row (what Step 4 will write)

One row carries both questions for one setup, so the state is tokenized once:

```json
{
  "state": {"ret_1d": 0.0008, "ret_5d": -0.0313, "ret_10d": -0.003, "ret_20d": 0.0717,
            "vol_20d": 0.0108, "close_to_ma50": 1.0394, "close_to_ma200": 1.0201},
  "questions": {
    "hit_target": {"type": "noul",
                   "instructions": "Will the price hit +5% before -3% within 10 trading days?"},
    "action": {"type": "choice", "instructions": "Action: buy or hold?",
               "criteria": ["buy", "hold"]}
  },
  "gold": {
    "hit_target": {"probabilities": {"true": 1.0, "false": 0.0}},
    "action": {"probabilities": {"buy": 1.0, "hold": 0.0}}
  }
}
```

Equivalent with `expected` instead of `gold`: `"expected": {"hit_target": true, "action": "buy"}`.

## Differences from what SPEC Step 4 assumes

SPEC section 5a describes a row as `questions = ["..."]` (a list of strings) and `gold = label` (a plain 1/0 or `"buy"`). The real schema differs in format:

1. `questions` is a dict of question id → definition (`type`, `instructions`, `criteria`), not a list of strings. A list makes `items_from_rows` fail (`.items()` on a list).
2. The question type lives inside each definition (`"type": "noul"`), not in the row.
3. `gold` is a dict keyed by question id, each holding `{"probabilities": {...}}`. A plain label goes in `expected` instead, also keyed by question id.
4. Both questions for one setup can share one row. SPEC 5a.4 counts rows as "train setups × questions per setup". With one row per setup, the check becomes: rows = train setups, items = rows × 2.

The labels and question wording do not change: label 1 → noul `true`, choice `buy`; label 0 → noul `false`, choice `hold`. Per SPEC 5a.3, Step 4 follows this schema.

## Things the fine-tune does that matter for later steps

- It holds out its own calibration slice: `min(400, 10% of items)`, chosen randomly with a fixed seed. That slice is taken from the training file, so calibration is on train-split data, not validation. PLAN Phase 3 says to fit temperatures on the validation split. That needs a separate step after fine-tuning.
- An optional `eval_data` file gives before/after metrics. Do not point it at test-split data.
- With only a few hundred or thousand items, the code warns that predictions can collapse to the class prior ("try more epochs, more data"). Our train split will be small (see the note below), so this is worth watching.

- Default settings in `TrainConfig`: 4 epochs, micro-batch 8, grad-accum 8. SPEC 5b quotes the Kaggle notebook's defaults (micro-batch 2, grad-accum 16), which are separate.

## Note on training-set size (resolved 2026-10-10)

With price history starting 2024-10-01, the 200-day moving average dropped every setup before mid-July 2025, and the train split kept only 455 setups. Price history now starts 2023-10-01 (SPEC change log), so features exist from the first train date. The train split is still small for a language-model fine-tune, so the collapse warning above is still worth watching.
