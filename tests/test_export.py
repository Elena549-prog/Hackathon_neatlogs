"""Step 4a tests: the Laya export holds train rows only, in Laya's format, with the right labels."""
import json
import os

import pandas as pd
import pytest

from src.export_laya import OUT_PATH, QUESTIONS, rows_for_setup
from src.features import FEATURE_NAMES
from src.labels import SETUPS_PATH

TRAIN_END = "2025-12-31"


def example_setup(label=1, date="2025-08-01"):
    row = {"ticker": "AAPL", "date": date, "split": "train", "label": label}
    row.update({name: 0.0123456 for name in FEATURE_NAMES})
    return pd.Series(row)


# ------------------------------------------------------------------ format, on a made-up setup

def test_two_rows_per_setup_one_question_each():
    rows = rows_for_setup(example_setup())
    assert len(rows) == len(QUESTIONS)
    assert sorted(q for r in rows for q in r["questions"]) == sorted(QUESTIONS)


@pytest.mark.parametrize("label,noul,choice", [(1, "true", "buy"), (0, "false", "hold")])
def test_label_maps_to_gold(label, noul, choice):
    rows = {next(iter(r["questions"])): r for r in rows_for_setup(example_setup(label))}
    assert rows["hit_target"]["gold"]["hit_target"]["probabilities"][noul] == 1.0
    assert rows["action"]["gold"]["action"]["probabilities"][choice] == 1.0


def test_state_holds_only_features_not_ticker_or_date():
    state = rows_for_setup(example_setup())[0]["state"]
    assert sorted(state) == sorted(FEATURE_NAMES)


def test_rows_pass_laya_validation():
    """The same checks laya.train.finetune runs on every question before training."""
    from laya.train import target_from_gold, to_internal
    for r in rows_for_setup(example_setup()):
        for qid, qdef in r["questions"].items():
            target = target_from_gold(to_internal(qid, qdef), r["gold"][qid])
            assert sum(target) == pytest.approx(1.0)


# ------------------------------------------------------------------- the real exported file

@pytest.fixture(scope="module")
def exported():
    if not os.path.exists(OUT_PATH):
        pytest.skip("%s not built yet (run python src/export_laya.py)" % OUT_PATH)
    with open(OUT_PATH, encoding="utf-8") as f:
        return [json.loads(line) for line in f]


def test_no_row_dated_after_train_end(exported):
    assert max(r["meta"]["date"] for r in exported) <= TRAIN_END


def test_only_train_split(exported):
    assert {r["meta"]["split"] for r in exported} == {"train"}


def test_row_count_matches_train_setups(exported):
    setups = pd.read_csv(SETUPS_PATH)
    assert len(exported) == (setups["split"] == "train").sum() * len(QUESTIONS)


def test_labels_match_setups_table(exported):
    setups = pd.read_csv(SETUPS_PATH)
    labels = {(t, d): l for t, d, l in setups[["ticker", "date", "label"]].itertuples(index=False)}
    for r in exported:
        m = r["meta"]
        assert labels[(m["ticker"], m["date"])] == m["label"]
        qid = next(iter(r["gold"]))
        key = "true" if qid == "hit_target" else "buy"
        assert r["gold"][qid]["probabilities"][key] == float(m["label"])


def test_eval_export_refuses_test_split(tmp_path):
    from src.export_laya import export_eval
    setups = pd.DataFrame([example_setup().to_dict()])
    with pytest.raises(ValueError):
        export_eval(setups, "test", str(tmp_path / "x.jsonl"))
