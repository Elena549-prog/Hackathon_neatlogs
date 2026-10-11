# Swarm cost cut: before and after

Evidence for the swarm cost controls in `docs/SWARM_SPEC.md` section 15. The originals live in the gitignored `runs/`; these are byte-for-byte copies.

| File | What it is |
|---|---|
| `swarm_smoke_30.jsonl` | Copy of `runs/swarm_smoke2.jsonl`: one decision per setup for the first 30 validation setups (`verdict` is `skipped` when the watcher did not wake the swarm) |
| `summary.md` | Copy of `runs/swarm_summary.md`: the summary table `src/swarm.py` wrote for that run |

## What was compared

| | Before | After |
|---|---|---|
| Run | Full validation run (`results/README.md`), resumed pass | Smoke run of the first 30 validation setups |
| Swarm behavior | Every setup decided by the swarm, two Planner rounds each (`rounds` is 2 on all 577 lines of `results/swarm_validation.jsonl`) | Price watcher wakes the swarm only on a 1-day move of at least 1.5 x 20-day vol; round 2 only for fixable failures |
| Setups | 310 (the resumed pass re-decided 62 errors and 248 setups not yet reached) | 30; 8 woke the swarm, 22 skipped with no LLM call |
| LLM cost logged | $11.76 | $0.1972 |
| Cost per setup | $0.038 | $0.0066 ($0.0247 per woken setup) |
| Errors | 0 in the final file | 0 |

## How the numbers were derived

- Before: $11.76 from `results/README.md` ("Cost"), divided by 310 = 62 + 248 setups of the resumed pass (same file, "How it was run") = $0.0379.
- After: $0.1972 from `summary.md` ("LLM cost"). Woken setups = lines of `swarm_smoke_30.jsonl` with `verdict` not `skipped` = 8 of 30. $0.1972 / 30 = $0.0066; per woken setup $0.0247 as printed in `summary.md`.

## Caveats

- Costs are upper bounds at DeepSeek peak cache-miss prices.
- The after-sample is small: 30 setups, all AAPL, dated 2026-01-02 to 2026-02-13.
- Before and after are different setup sets.
- This measures cost, not decision quality.
