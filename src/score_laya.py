"""Score Laya on the validation split, measured the same way as src/baselines.py.

Self-contained (needs only laya, numpy, scikit-learn) so it can be uploaded to Kaggle as one file.
Scores the original model (zero-shot) and the fine-tuned checkpoint side by side.

On Kaggle (GPU on, internet on, laya installed, the fine-tuned model in /kaggle/working):
    !python /kaggle/input/<dataset>/score_laya.py \
        --data /kaggle/input/<dataset>/laya_validation.jsonl \
        --models convaiinnovations/laya /kaggle/working/laya_finetuned

Locally: python src/score_laya.py --models convaiinnovations/laya runs/checkpoints/laya_finetuned

Prints a table and writes laya_validation_scores.json (all predictions) next to --out.
"""
import argparse
import json
import os
import time

import numpy as np
from sklearn.metrics import brier_score_loss, log_loss, roc_auc_score

# Must match src/export_laya.py exactly: the fine-tuned model was trained on this wording.
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
SEED, N_BOOT, BLOCK_DAYS = 0, 2000, 10   # same as src/baselines.py


def read_rows(path):
    with open(path, encoding="utf-8") as f:
        rows = [json.loads(line) for line in f if line.strip()]
    splits = {r["meta"]["split"] for r in rows}
    if "test" in splits:
        raise SystemExit("refusing to score test-split rows (SPEC section 0)")
    return rows


def predict(model_path, states, batch_size):
    import laya
    agent = laya.load(model_path)
    t0 = time.time()
    results = agent.predict_batch(states, QUESTIONS, batch_size=batch_size)
    secs = time.time() - t0
    p_yes = np.array([r["answers"]["hit_target"]["noul"] for r in results], dtype=float)
    p_buy = np.array([r["answers"]["action"]["probabilities"]["buy"] for r in results], dtype=float)
    return p_yes, p_buy, secs


def block_auc_interval(dates, y, p):
    """90% AUC interval from a bootstrap over 10-trading-day blocks, as in src/baselines.py."""
    uniq = sorted(set(dates))
    block_of = {d: i // BLOCK_DAYS for i, d in enumerate(uniq)}
    blocks = np.array([block_of[d] for d in dates])
    idx_by_block = [np.flatnonzero(blocks == b) for b in np.unique(blocks)]
    rng = np.random.default_rng(SEED)
    aucs = []
    for _ in range(N_BOOT):
        idx = np.concatenate([idx_by_block[b] for b in rng.integers(0, len(idx_by_block), len(idx_by_block))])
        if len(np.unique(y[idx])) == 2:
            aucs.append(roc_auc_score(y[idx], p[idx]))
    return np.percentile(aucs, 5), np.percentile(aucs, 95)


def row(name, y, p, dates, base_brier):
    p = np.clip(p, 1e-6, 1 - 1e-6)
    lo, hi = block_auc_interval(dates, y, p)
    brier = brier_score_loss(y, p)
    return {"model": name, "auc": roc_auc_score(y, p), "auc_lo": lo, "auc_hi": hi, "brier": brier,
            "brier_skill": 1 - brier / base_brier, "logloss": log_loss(y, p, labels=[0, 1]),
            "accuracy": float(np.mean((p >= 0.5) == y)), "mean_p": float(p.mean())}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data/laya_validation.jsonl")
    ap.add_argument("--models", nargs="+", default=["convaiinnovations/laya", "runs/checkpoints/laya_finetuned"])
    ap.add_argument("--out", default="laya_validation_scores.json")
    ap.add_argument("--batch-size", type=int, default=32)
    args = ap.parse_args()

    rows = read_rows(args.data)
    states = [r["state"] for r in rows]
    y = np.array([r["meta"]["label"] for r in rows])
    dates = [r["meta"]["date"] for r in rows]
    base = rows[0]["meta"]["train_base_rate"]
    base_brier = brier_score_loss(y, np.full(len(y), base))

    table = [{"model": "Base rate (%.1f%%)" % (100 * base), "auc": 0.5, "auc_lo": None, "auc_hi": None,
              "brier": base_brier, "brier_skill": 0.0,
              "logloss": log_loss(y, np.full(len(y), base), labels=[0, 1]),
              "accuracy": float(np.mean(y == int(base >= 0.5))), "mean_p": base}]
    preds = {}
    for m in args.models:
        p_yes, p_buy, secs = predict(m, states, args.batch_size)
        label = "fine-tuned" if os.path.isdir(m) else "zero-shot"
        print("%s (%s): %d states in %.1f s" % (m, label, len(states), secs), flush=True)
        table.append(row("Laya %s, yes/no question" % label, y, p_yes, dates, base_brier))
        table.append(row("Laya %s, buy/hold question" % label, y, p_buy, dates, base_brier))
        preds[m] = {"p_yes": p_yes.round(4).tolist(), "p_buy": p_buy.round(4).tolist()}

    print("\nValidation split: %d setups, positive rate %.1f%%. Test split not used.\n" % (len(y), 100 * y.mean()))
    print("| Model | AUC | AUC 90% interval | Brier | Brier skill vs base rate | Log loss | Accuracy | Mean prob |")
    print("|---|---|---|---|---|---|---|---|")
    for t in table:
        ci = "%.3f to %.3f" % (t["auc_lo"], t["auc_hi"]) if t["auc_lo"] is not None else "-"
        print("| %s | %.3f | %s | %.4f | %+.1f%% | %.4f | %.1f%% | %.3f |" % (
            t["model"], t["auc"], ci, t["brier"], 100 * t["brier_skill"], t["logloss"],
            100 * t["accuracy"], t["mean_p"]))

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump({"table": table, "ids": [r["meta"] for r in rows], "predictions": preds}, f, default=float)
    print("\nAll predictions written to %s" % args.out)


if __name__ == "__main__":
    main()
