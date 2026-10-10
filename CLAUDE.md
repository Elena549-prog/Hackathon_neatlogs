# CLAUDE.md

This repo is a hackathon project: a paper-trading agent swarm with a Laya accuracy layer.

## Where to start
- `docs/HANDOVER.md` (on branch `step-1-4`): current status, results, decisions and the next step. **Read this first when picking up the work.**
- `docs/PLAN.md`: the approved plan (goal, phases, fallback).
- `GUIDE.md`: the 13-step guide for the whole project.
- `docs/SPEC.md`: the detailed spec for Steps 1–4 (schema check, price data, labels and splits, Laya export and Kaggle fine-tune). **If asked to start work, begin with `docs/SPEC.md`.**

## Ground rules
- Paper trading and historical replay only. No live trading, no real money, no personalized financial advice.
- Follow `docs/SPEC.md` exactly. Frozen values in its section 0 do not change.
- Never look at test-split labels or results.
- Never commit secrets (Kaggle tokens, API keys, `.env`). Use environment variables.
- Commit after each step. Work on a branch, not `main`.
- If a step is blocked or ambiguous, stop and report instead of guessing.
