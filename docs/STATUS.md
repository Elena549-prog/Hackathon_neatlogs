# Status (2026-10-11, end of the foundation session)

Read this first in a new session. Code is complete through M2 and M3; what is left is the real runs, the recording and the posts. Branch with this work: `claude/model-build-complete-ec91ad` (on top of `main` 88aab22, which holds Elena's M1 + M3 merges).

## Where things stand

| Area | State |
|---|---|
| Strategy Auditor (`src/auditor/`) | **Built through M2.** M1 (Elena, branch `m1-auditor`): Planner with frozen plan v0 (SHA-256), data tools, gap-aware backtests, bootstrap, baselines, paired lower bound, stricter cost, tail risk, 7 coded checks, verdict rules, template report, registry, `events.jsonl`, `--resume`, 8-call budget, `--fault`, balance check. **M2 (2026-10-11, this branch):** Naysayer call 1 picks up to 3 follow-ups from F1–F4 (`src/auditor/followups.py`), the Mathematician runs them in code on v0, Naysayer call 2 critiques with their results, and a met rule downgrades `promising` → `inconclusive` only. `--no-followups` reproduces the M1 behaviour for the before/after runs. No real DeepSeek audit has run yet. |
| Mission-control UI (M3) | Built in replay mode (Elena, `m3-ui`), plus the **Objections panel** (2026-10-11): coded-check cards and follow-up cards (REQUESTED → result → NO DOWNGRADE / SKIPPED / RULE MET, then APPLIED or NOT APPLIED once the verdict arrives). Checked in the browser at 1920×1080 with a fake-LLM real-data replay and with the synthetic fixture at 1920×1080 and 1280×800. At 1280 wide the agent graph labels are small (about 7 px); fine at 1920. Needs a real demo audit in `results/audits/` before the video. |
| cfo.ai | `results/business_model.xlsx` **reworked per audit** (2026-10-11): one cost cell `Assumptions!B5` = $0.048 per audit (ESTIMATE, arithmetic on the `Cost_Estimate` sheet), pay-per-audit and hobbyist plan hypotheses, unit economics, base and growth scenarios. `verify_model.py` evaluates all 763 formulas (pycel) and cross-checks them in Python. Steps and Ari prompts: `docs/CFO_AI.md`. Not yet pushed into cfo.ai itself. |
| Trading swarm (`src/swarm.py`, `src/agents/`) | Built, validation run done: 1 of 577 approved (`results/`). New `--final-test` flag (2026-10-11): the one allowed test-split run; refuses `--limit`, an existing output without `--resume`, and any committed `results/swarm_test*`. **Not run.** |
| Cost cuts (swarm) | $0.038 → $0.0066 per setup (`results/swarm_cost_cut/`). |
| DeepSeek | Key in `.env`. Balance on 2026-10-11: **$4.37** (the auditor refuses below $2). Estimate $0.048 per audit, so the 7 demo audits cost about $0.35. |
| neatlogs | Working. **The old key must still be rotated** (it was printed by the old SDK in session 1). |
| Entire | Enabled, `push_sessions` false until the neatlogs key is rotated. |
| Laya | Fine-tune done on Kaggle (Elena). Validation scoring not run: the checkpoint lives only in Elena's Kaggle notebook (`docs/HANDOVER.md` Route A). Expected near AUC 0.5. Stretch only (spec section 15). |
| Tests | `pytest tests/`: 266 pass, 1 expected failure (`test_export.py` needs the `laya` package). UI: 28 vitest tests, typecheck, lint, build pass. |

## Demo day: run order

Run from the main checkout (`D:\zeesh\projects\trading-swarm`, which has `.env`, `.venv` and the warm `data/cache/`) after merging this branch. Each step is one command; the real audits use DeepSeek.

1. Housekeeping (Zeeshan, by hand): rotate the neatlogs key in `.env`, then set Entire `push_sessions` to true and check `entire checkpoint list`.
2. Post #1 (#neatHack) with the written expectations for the three demo ideas (spec section 13): dips `kill`; tech straddles before earnings `kill`; selling low-vol mega-cap straddles: positive mean, tail risk decides.
3. Before runs (M1 behaviour, no follow-ups), then commit and tag:
   ```
   .venv/Scripts/python.exe scripts/demo_audits.py before
   git add results/audits && git commit -m "Demo audits: before (M1, no follow-ups)" && git tag before
   ```
4. After runs (M2, follow-ups), then commit and tag:
   ```
   .venv/Scripts/python.exe scripts/demo_audits.py after
   git add results/audits && git commit -m "Demo audits: after (M2, follow-ups)" && git tag after
   ```
   `results/audits/before_after.md` is the before/after table (verdict, downgrades with reasons, follow-ups, LLM calls, cost, wall time). Cross-check the costs in neatlogs.
5. Recovery beat: `.venv/Scripts/python.exe scripts/demo_audits.py fault` (tech straddles with `--fault dolthub_timeout`; the report and UI label it INJECTED).
6. cfo.ai: put the mean measured cost per audit (after runs, `cost.usd` in each `state.json`) into `Assumptions!B5`, rebuild with `python scripts/spikes/build_business_model.py results/business_model.xlsx`, verify with `python scripts/spikes/verify_model.py`, and build it in cfo.ai per `docs/CFO_AI.md`.
7. Record: `cd ui && npm ci && npm run build`, then `.venv/Scripts/python.exe -m uvicorn src.auditor.server:app --port 8000`, open http://127.0.0.1:8000/ at 1920×1080, click a demo chip (it replays the matching recorded audit), 4× or 8×. Video beats: spec section 13.
8. Posts #2 (first verdict + a neatlogs trace) and #3 (before/after table).
9. Optional, needs Elena's Kaggle: Laya scores (`docs/HANDOVER.md` Route A) and the go/no-go. Optional, only after freezing the swarm config in `results/README.md`: the one swarm test run, `.venv/Scripts/python.exe -m src.swarm --split test --final-test --workers 8` (about $9, 35 min; `--resume` only if it stops).

Spend cap: at most 25 real audits before the freeze; the demo plan uses 7.

### Fake-LLM runs on real data (development evidence only; never record these)

Keyword planner and keyword Naysayer (it asks for all four follow-ups, so the cap of 3 and the stock_long-only F3 rule are exercised), real Yahoo and DoltHub data, no model calls. Run 2026-10-11 on this branch; the caches they filled are in the main checkout's `data/cache/` (prices, `earnings.csv`, `iv.csv`), so the real runs start warm.

| Idea | Wall time | Verdict | Follow-ups |
|---|---|---|---|
| buy dips in an uptrend | 50 s (cold price and earnings download) | inconclusive: lower bound −0.31%, paired lower bound −0.62% (validation n 282) | F1 +0.22% over 258 trades, F2 opposite sign in 1 of 11 train years, F3 +0.18% (5 days) / +0.26% (20 days): no rule met; F4 not run (cap) |
| buy straddles on tech before earnings | 12 min 51 s cold (190 DoltHub windows, 4 threads; now in `data/cache/iv.csv`), 2 s warm | kill: validation mean −18.38% over 34 trades, stricter-cost lower bound −1.03% | F1 no trades left (the idea is earnings), rule not evaluated; F2 0 of 6 years opposite; F4 −23.00% without the top ticker (rule met, but follow-ups never change a kill); F3 not run (straddles) |
| sell straddles on low-volatility mega-caps | 2 s warm | inconclusive: validation n 20 < 30 | F1 +4.89% over 16 trades; F2 opposite sign in 4 of 6 train years (rule met); F4 −27.02% without the top ticker (rule met); a promising base result would have been downgraded twice |

## Running things

- Python: `.venv/Scripts/python.exe` (3.12; the venv has no pip, install with `uv pip install --python .venv/Scripts/python.exe -r requirements.txt`). Tests: `.venv/Scripts/python.exe -m pytest tests/ -q --basetemp=.pytest_tmp`.
- Keys live in `.env` (gitignored). Never print them.
- Entire: `$HOME/.local/bin/entire.exe` (`entire checkpoint list`).
- Strategy Auditor: `.venv/Scripts/python.exe -m src.auditor "<idea>"` (DeepSeek; refuses below a $2 balance; `--no-balance-check` if the balance API is down), `--provider fake` for development (report says FAKE LLM), `--no-followups` (M1 behaviour), `--resume <audit_id>`, `--fault dolthub_timeout|llm_empty`, `--id <audit_id>`. Outputs in `runs/audits/<id>/`; caches in `data/cache/`.
- Mission control: `.venv/Scripts/python.exe -m uvicorn src.auditor.server:app --port 8000` serves the API and the built UI. Dev: `cd ui && npm run dev` (proxies `/api` to :8000). UI checks: `cd ui && npm test && npm run typecheck && npm run lint && npm run build`. Synthetic fixture (never record it): `.venv/Scripts/python.exe scripts/synthetic_audit.py --out runs/audits`. `.claude/launch.json` uses the Mac path `.venv/bin/python`; on Windows start the server by hand.
- Follow-up interpretation choices (spec section 4 leaves them open): F1 drops v0's trades whose own holding window (entry, entry + hold] holds a report date and opens no new trades in their place; F3's `train`/`validation` in the event are the 5-day run, both runs are in `variants`; F4's result text never names the ticker (the Naysayer sees no tickers), the ticker is a separate field shown in the report.
