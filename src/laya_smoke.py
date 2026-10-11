"""Step 1 smoke test: does the Laya row format we documented actually work?

1. Builds 20 dummy rows in Laya's fine-tuning format ({state, questions, gold}).
   The numbers are random and the labels are fake: this checks the plumbing, not accuracy.
2. Feeds them to Laya's own training loader (laya.train.dry_run) to confirm it accepts them
   without skipping any.
3. Runs the untrained (zero-shot) model on each row and times every question.

Writes the dummy rows to runs/dummy_rows.jsonl and the timings to runs/zero_shot_smoke.md.
Usage: python src/laya_smoke.py            (full run; downloads the model from Hugging Face)
       python src/laya_smoke.py --offline  (format check only; no download)
"""
import json
import os
import platform
import random
import statistics
import sys
import time

import laya
from laya.train import TrainConfig, dry_run, target_from_gold, to_internal

N_ROWS = 20
MODEL = "convaiinnovations/laya"
OUT_DIR = "runs"

# The two questions from SPEC section 5a, written in the shape Laya requires.
QUESTIONS = {
    "hit_target": {
        "type": "noul",
        "instructions": "Will the price hit +5% before -3% within 10 trading days?",
    },
    "action": {
        "type": "choice",
        "instructions": "Action: buy or hold?",
        "criteria": ["buy", "hold"],
    },
}


def dummy_features(rng):
    """Fake feature values with the same names Step 3 will produce."""
    return {
        "ret_1d": round(rng.gauss(0, 0.015), 4),
        "ret_5d": round(rng.gauss(0, 0.03), 4),
        "ret_10d": round(rng.gauss(0, 0.045), 4),
        "ret_20d": round(rng.gauss(0, 0.06), 4),
        "vol_20d": round(abs(rng.gauss(0.018, 0.005)), 4),
        "close_to_ma50": round(rng.gauss(1.0, 0.04), 4),
        "close_to_ma200": round(rng.gauss(1.05, 0.08), 4),
    }


def gold_for(label):
    """Hard (one-hot) gold distributions for a 0/1 label, keyed as laya.train expects."""
    return {
        "hit_target": {"probabilities": {"true": float(label), "false": float(1 - label)}},
        "action": {"probabilities": {"buy": float(label), "hold": float(1 - label)}},
    }


def main():
    rng = random.Random(0)
    os.makedirs(OUT_DIR, exist_ok=True)
    rows = []
    for _ in range(N_ROWS):
        label = rng.randint(0, 1)
        rows.append({"state": dummy_features(rng), "questions": QUESTIONS, "gold": gold_for(label)})
    rows_path = os.path.join(OUT_DIR, "dummy_rows.jsonl")
    with open(rows_path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")

    # Offline format check: the validation and target-building functions finetune() runs on
    # every row, before tokenizing. Needs no model download.
    n_ok = 0
    for r in rows:
        for qid, qdef in r["questions"].items():
            q = to_internal(qid, qdef)
            target_from_gold(q, r["gold"][qid])
            n_ok += 1
    print("offline format check: %d/%d items valid" % (n_ok, N_ROWS * len(QUESTIONS)))
    if "--offline" in sys.argv:
        return

    # Loader check: the same code path finetune() uses, without training (downloads the tokenizer).
    summary = dry_run(rows_path, MODEL, TrainConfig())
    if summary["valid_items"] != N_ROWS * len(QUESTIONS) or summary["skipped"]:
        sys.exit("loader rejected rows: %r" % (summary,))

    agent = laya.load(MODEL)
    agent.system_one(rows[0]["state"], QUESTIONS)  # warm-up, not timed

    per_row_ms, results = [], []
    for r in rows:
        t0 = time.perf_counter()
        out = agent.system_one(r["state"], QUESTIONS)
        per_row_ms.append((time.perf_counter() - t0) * 1000)
        results.append(out)
    per_q = [ms / len(QUESTIONS) for ms in per_row_ms]

    first = results[0]
    lines = [
        "# Zero-shot smoke test (Step 1)",
        "",
        "Dummy data only: 20 rows of random feature values with random labels. "
        "These numbers check that the format works and how fast Laya answers; "
        "they say nothing about accuracy.",
        "",
        "| Item | Value |",
        "|---|---|",
        "| Laya version | %s |" % laya.__version__,
        "| Model | %s |" % MODEL,
        "| Device | %s |" % agent.device,
        "| Machine | %s, Python %s |" % (platform.machine(), platform.python_version()),
        "| Rows | %d (x %d questions = %d items) |" % (N_ROWS, len(QUESTIONS), N_ROWS * len(QUESTIONS)),
        "| Loader check (laya.train.dry_run) | %d valid items, skipped %r |"
        % (summary["valid_items"], summary["skipped"]),
        "| Latency per question, mean | %.1f ms |" % statistics.mean(per_q),
        "| Latency per question, median | %.1f ms |" % statistics.median(per_q),
        "| Latency per question, max | %.1f ms |" % max(per_q),
        "",
        "Latency is wall time of one `system_one` call (both questions in one forward pass) "
        "divided by 2, after one untimed warm-up call.",
        "",
        "## Example: row 1",
        "",
        "```json",
        json.dumps({"state": rows[0]["state"], "gold": rows[0]["gold"]}, indent=2),
        "```",
        "",
        "Laya output:",
        "",
        "```json",
        json.dumps(first, indent=2, default=str),
        "```",
    ]
    with open(os.path.join(OUT_DIR, "zero_shot_smoke.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print("\n".join(lines[:20]))


if __name__ == "__main__":
    main()
