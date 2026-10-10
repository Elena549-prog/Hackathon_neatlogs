"""Step 4b alternative: fine-tune Laya on our own rows with the library's training loop.

UNTESTED: the cloud workspace this was written in cannot download the Laya model from
Hugging Face. Run it on Kaggle (or any machine with internet and ideally a GPU).

Why not the notebook named in SPEC 5b: notebooks/laya_finetune_typed_decisions_2xT4_kaggle.ipynb
trains on the public `LocalLLaMA/typed-decisions` dataset via `load_dataset(...)`, not on an
uploaded file, and expects state/questions/gold as JSON strings. `laya.train.finetune` reads our
JSONL directly in the format documented in docs/laya_schema.md. Settings are the library
defaults (TrainConfig: 4 epochs, micro-batch 8, grad-accum 8); none are changed here.

On Kaggle (GPU T4 accelerator, internet on), in a notebook:
    !pip install -q laya
    # upload data/laya_train.jsonl as a private dataset, then:
    !python finetune_laya.py --data /kaggle/input/<your-dataset>/laya_train.jsonl \
        --out /kaggle/working/laya_finetuned

Locally: python src/finetune_laya.py   (defaults below)
"""
import argparse
import json
import time

from laya.train import TrainConfig, finetune

MODEL_ID = "convaiinnovations/laya"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data/laya_train.jsonl")
    ap.add_argument("--out", default="runs/checkpoints/laya_finetuned")
    ap.add_argument("--model", default=MODEL_ID)
    args = ap.parse_args()

    start = time.time()
    print("UTC start: %s" % time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(start)), flush=True)
    summary = finetune(args.data, args.model, args.out, TrainConfig())
    print("finished in %.1f min" % ((time.time() - start) / 60), flush=True)

    keep = {k: summary[k] for k in ("train_items", "calibration_items", "skipped", "epoch_loss",
                                    "temperature", "calibration", "output_dir")}
    print(json.dumps(keep, indent=2, default=str))


if __name__ == "__main__":
    main()
