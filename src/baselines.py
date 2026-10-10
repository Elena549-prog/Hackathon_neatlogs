"""Baseline comparison: how much do simple models learn from our 7 price features?

Usage (from the repo root, after Step 3): python src/baselines.py

Trains on the train split, scores on the validation split. The test split is never read.
Writes runs/baselines.md. Not part of SPEC Steps 1-4: it sets the bar Laya must beat.

Settings are fixed in advance and not tuned on validation, so the validation scores are
an honest estimate rather than the best of many tries.
"""
import os
import sys

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, log_loss, roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.features import FEATURE_NAMES
from src.labels import SETUPS_PATH

REPORT_PATH = os.path.join("runs", "baselines.md")
SEED = 0
N_BOOT = 2000
BLOCK_DAYS = 10  # bootstrap in blocks of 10 trading days: neighbouring setups share future prices


class BaseRate:
    """Predicts the train positive rate for everyone. Learns nothing from the features."""

    def fit(self, X, y):
        self.p = float(np.mean(y))
        return self

    def predict_proba(self, X):
        return np.column_stack([np.full(len(X), 1 - self.p), np.full(len(X), self.p)])


def models():
    return {
        "Base rate": BaseRate(),
        "Logistic regression": make_pipeline(StandardScaler(), LogisticRegression(C=1.0, max_iter=1000)),
        "Random forest": RandomForestClassifier(n_estimators=500, min_samples_leaf=20,
                                                max_features="sqrt", random_state=SEED, n_jobs=-1),
        "Gradient boosting": HistGradientBoostingClassifier(max_depth=3, learning_rate=0.05, max_iter=200,
                                                            min_samples_leaf=20, random_state=SEED),
    }


def scores(y, p):
    return {"auc": roc_auc_score(y, p), "brier": brier_score_loss(y, p), "logloss": log_loss(y, p, labels=[0, 1])}


def block_bootstrap(dates, y, preds, n_boot=N_BOOT, seed=SEED):
    """90% intervals for AUC and Brier, resampling blocks of consecutive trading days."""
    uniq = np.sort(dates.unique())
    block_of_date = {d: i // BLOCK_DAYS for i, d in enumerate(uniq)}
    blocks = dates.map(block_of_date).to_numpy()
    idx_by_block = [np.flatnonzero(blocks == b) for b in np.unique(blocks)]
    rng = np.random.default_rng(seed)
    out = {name: {"auc": [], "brier": []} for name in preds}
    for _ in range(n_boot):
        idx = np.concatenate([idx_by_block[b] for b in rng.integers(0, len(idx_by_block), len(idx_by_block))])
        if len(np.unique(y[idx])) < 2:
            continue
        for name, p in preds.items():
            out[name]["brier"].append(brier_score_loss(y[idx], p[idx]))
            if name != "Base rate":
                out[name]["auc"].append(roc_auc_score(y[idx], p[idx]))
    return {name: {k: (np.percentile(v, 5), np.percentile(v, 95)) if v else None for k, v in m.items()}
            for name, m in out.items()}


def main():
    setups = pd.read_csv(SETUPS_PATH)
    train = setups[setups["split"] == "train"]
    val = setups[setups["split"] == "validation"].reset_index(drop=True)
    X_tr, y_tr = train[FEATURE_NAMES].to_numpy(), train["label"].to_numpy()
    X_va, y_va = val[FEATURE_NAMES].to_numpy(), val["label"].to_numpy()

    preds, rows = {}, []
    for name, model in models().items():
        p = model.fit(X_tr, y_tr).predict_proba(X_va)[:, 1]
        preds[name] = p
        rows.append((name, scores(y_va, p)))
    ci = block_bootstrap(val["date"], y_va, preds)
    base_brier = dict(rows)["Base rate"]["brier"]

    lines = [
        "# Baseline comparison (validation split)", "",
        "Trained on %d train setups (positive rate %.1f%%), scored on %d validation setups "
        "(positive rate %.1f%%). Test split not used." % (len(train), 100 * y_tr.mean(), len(val), 100 * y_va.mean()),
        "", "| Model | AUC | AUC 90% interval | Brier | Brier skill vs base rate | Log loss |",
        "|---|---|---|---|---|---|",
    ]
    for name, s in rows:
        auc_ci = ci[name]["auc"]
        lines.append("| %s | %.3f | %s | %.4f | %+.1f%% | %.4f |" % (
            name, s["auc"], "%.3f to %.3f" % auc_ci if auc_ci else "-",
            s["brier"], 100 * (1 - s["brier"] / base_brier), s["logloss"]))
    lines += [
        "", "How to read this:",
        "- AUC 0.5 = no better than random at ranking winners above losers; 1.0 = perfect.",
        "- Brier skill > 0 means the probabilities are closer to the outcomes than always saying "
        "the train base rate; < 0 means worse.",
        "- Intervals: block bootstrap over %d-day blocks of validation dates, %d resamples. "
        "Neighbouring setups overlap in time, so this is wider (more honest) than a plain bootstrap."
        % (BLOCK_DAYS, N_BOOT),
        "", "Settings (fixed before looking at validation): logistic C=1.0 on standardized features; "
        "random forest 500 trees, min 20 per leaf; gradient boosting depth 3, 200 rounds, rate 0.05, "
        "min 20 per leaf.",
    ]
    report = "\n".join(lines) + "\n"
    os.makedirs(os.path.dirname(REPORT_PATH), exist_ok=True)
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write(report)
    print(report)


if __name__ == "__main__":
    main()
