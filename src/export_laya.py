"""Step 4a: turn the train split into Laya fine-tuning rows.

Usage (from the repo root, after Step 3):
    python src/export_laya.py               train rows for fine-tuning
    python src/export_laya.py --validation  validation states for scoring (src/score_laya.py)

Reads data/labels/setups.csv, keeps split == "train" only, and writes data/laya_train.jsonl.
Row format: docs/laya_schema.md. One row per question, so each setup gives two rows
(SPEC 5a.4: rows = train setups x questions per setup).
"""
import json
import os
import random
import sys

import pandas as pd

if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.features import FEATURE_NAMES
from src.labels import SETUPS_PATH

OUT_PATH = os.path.join("data", "laya_train.jsonl")
DECIMALS = 4  # Laya reads the state as text; 4 decimals keeps it short without losing signal

# The questions from SPEC 5a, written in Laya's question format (docs/laya_schema.md).
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


def gold_for(qid, label):
    """Hard gold distribution for one question. label 1 -> true / buy, label 0 -> false / hold."""
    label = int(label)
    if qid == "hit_target":
        return {"probabilities": {"true": float(label), "false": float(1 - label)}}
    if qid == "action":
        return {"probabilities": {"buy": float(label), "hold": float(1 - label)}}
    raise KeyError(qid)


def rows_for_setup(setup):
    """The Laya rows for one setup: one per question.

    `meta` is ignored by Laya's loader (it reads only state/questions/gold) and is not shown
    to the model. It is kept so every row can be traced back to its setup and checked.
    """
    state = {name: round(float(setup[name]), DECIMALS) for name in FEATURE_NAMES}
    meta = {"ticker": setup["ticker"], "date": setup["date"], "split": setup["split"],
            "label": int(setup["label"])}
    return [{"state": state, "questions": {qid: q}, "gold": {qid: gold_for(qid, setup["label"])},
             "meta": meta}
            for qid, q in QUESTIONS.items()]


def export(setups, out_path=OUT_PATH):
    train = setups[setups["split"] == "train"]
    rows = [r for _, s in train.iterrows() for r in rows_for_setup(s)]
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    return train, rows


EVAL_PATH = os.path.join("data", "laya_validation.jsonl")


def export_eval(setups, split="validation", out_path=EVAL_PATH):
    """Rows for scoring Laya on a held-out split: the state plus meta, one row per setup.

    The label sits in `meta` so the scoring script can compare. Refuses the test split:
    SPEC section 0 forbids looking at results on it before the final evaluation.
    """
    if split == "test":
        raise ValueError("refusing to export the test split for scoring (SPEC section 0)")
    train_rate = float(setups.loc[setups["split"] == "train", "label"].mean())
    part = setups[setups["split"] == split]
    rows = [{"state": {name: round(float(s[name]), DECIMALS) for name in FEATURE_NAMES},
             "meta": {"ticker": s["ticker"], "date": s["date"], "split": split,
                      "label": int(s["label"]), "train_base_rate": round(train_rate, 4)}}
            for _, s in part.iterrows()]
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    return rows


def main():
    setups = pd.read_csv(SETUPS_PATH)
    if "--validation" in sys.argv:
        rows = export_eval(setups)
        print("validation rows written to %s: %d" % (EVAL_PATH, len(rows)))
        return
    train, rows = export(setups)
    expected = len(train) * len(QUESTIONS)
    print("train setups: %d, questions per setup: %d, rows written: %d (expected %d)"
          % (len(train), len(QUESTIONS), len(rows), expected))
    if len(rows) != expected:
        sys.exit("row count mismatch")
    print("\n3 random rows to check by hand:")
    for r in random.Random(0).sample(rows, 3):
        print(json.dumps(r))


if __name__ == "__main__":
    main()
