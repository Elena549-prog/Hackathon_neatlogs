# CLAUDE.md

This repo is a hackathon project: the Strategy Auditor, an agent team that tests trading ideas and returns an evidence-backed verdict. It builds on an earlier paper-trading agent swarm (same repo).

## Where to start
- `docs/STATUS.md` (branch `swarm`): latest status and next actions across all work. **Read this first.**
- `docs/AUDITOR_SPEC.md`: the Strategy Auditor, the main agent (spec approved 2026-10-11; build it next).
- `docs/HANDOVER.md` (on branch `step-1-4`): background on steps 1–4 (data, labels, Laya fine-tune). Done.
- `docs/PLAN.md`: the approved plan (goal, phases, fallback).
- `GUIDE.md`: the 13-step guide for the whole project.
- `docs/SPEC.md`: the spec for steps 1–4 (done). Its frozen values still apply to the data and labels.

## Ground rules
- Paper trading and historical replay only. No live trading, no real money, no personalized financial advice.
- For the trading swarm's data and labels (steps 1–4), follow `docs/SPEC.md` exactly; frozen values in its section 0 do not change. The Strategy Auditor follows `docs/AUDITOR_SPEC.md`, whose section 3 overrides SPEC section 0 for the auditor.
- Never look at test-split labels or results.
- Never commit secrets (Kaggle tokens, API keys, `.env`). Use environment variables.
- Commit after each step. Work on a branch, not `main`.
- If a step is blocked or ambiguous, stop and report instead of guessing.
