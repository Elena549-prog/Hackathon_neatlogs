# Submission: sponsor tools (neatlogs, cfo.ai, Entire)

Everything we did with the three sponsor tools, with links and IDs to paste into the submission. Details live in the files linked from each section.

## neatlogs: tracing every agent step

**What it does here.** Every audit and swarm decision is one neatlogs trace. Workflow, agent and tool steps are spans (`src/tracing.py`, neatlogs 1.4 on OpenTelemetry / OpenInference); LLM calls are recorded by neatlogs' OpenAI instrumentation and nest under the agent span that made them (`src/llm.py`). Failed tool calls are marked as errors on their span. Each `report.md` prints its trace ID in section 9.

Dashboard: project "Zeeshan's project", workflow `trading-swarm`.

| Run | Trace ID | Wrapper cost (upper bound) |
|---|---|---|
| after (M2): buy dips in an uptrend | `66f9d2d4745323068e43c84d01c9bad1` | $0.0466 |
| after (M2): buy straddles on tech before earnings | `d15017b0b19406f2ed867871071fab13` | $0.0222 |
| after (M2): sell straddles on low-vol mega-caps | `436ae42eabee193059af98ce63b6e3db` | $0.0365 |
| fault run: injected DoltHub timeout, recovered | `ddc14bc17377d6db8c9afa65359695b0` | $0.0274 |
| before (M1): buy dips | `94803f1af610b26a654915d8c031c83e` | $0.0232 |
| before (M1): buy straddles | `e8ced3b1fffa3b4d6e87f17f2d1aa10b` | $0.0174 |
| before (M1): sell straddles | `bc31519223fc7c69c530c8fef758d552` | $0.0161 |
| swarm: Naysayer v2 replay, AMZN 2026-07-30 (tag `naysayer-replay`) | `7b8501eaf5cdfa8d7918338e5a2e4cc0` | |

- **Measured cost per audit (neatlogs):** $0.0114, $0.0056 and $0.0085 for the three after-audits, mean **$0.0085**. The wrapper's own figure uses DeepSeek peak cache-miss prices, so it is an upper bound (mean $0.0351). The measured figure is the one fed into cfo.ai.
- **Recovery:** the fault run injects a DoltHub timeout; the data layer retries after 2 s and the audit completes (`results/audits/fault-dolthub/report.md`, section 8).
- **Before/after:** `results/audits/before_after.md`.

## cfo.ai: the business plan, priced per audit

Built natively in cfo.ai on 2026-10-12 (workspace "Zeeshan CFOAI"): pages Assumptions (20 editable inputs), Monthly model (Nov 2026 to Oct 2027), Unit economics and Summary; scenarios Base and Growth. Reconciled to `results/business_model.xlsx` to the cent, then the cost cell was set to the **measured $0.0085 per audit** from neatlogs.

Read-only share links (no login, all four pages):

- **Base:** https://app.cfo.ai/s/3gz1yhzF4-VhA24I
- **Growth:** https://app.cfo.ai/s/wSxyktuJXgE93MQJ

A link shows one scenario; workspace members see both side by side on the Summary page.

| At the measured $0.0085 per audit | Base | Growth |
|---|---|---|
| 12-month LLM cost | $35.80 (was $202.19 at the $0.048 estimate) | |
| Cash, end of month 12 | $2,193 | below zero in month 4 |
| Funding needed | $0 | $47,346 |

Reading: LLM cost would have to reach $1.88 per audit (220x the measured cost) before a $2 audit stops contributing. The plan is decided by users, churn, CAC and team cost, not by inference. Method, inputs and Ari prompts: `docs/CFO_AI.md`.

## Entire: checkpoints of how it was built

Built with Claude Code with Entire enabled (`.entire/settings.json`). Three commits carry an `Entire-Checkpoint` trailer that links the code change to the session that produced it:

| Commit | Change | Checkpoint |
|---|---|---|
| [92918c8](https://github.com/Elena549-prog/Hackathon_neatlogs/commit/92918c8fff7d781bbc241abdc0b52a8e49baf40f) | M2 follow-ups, Objections panel, `--final-test`, per-audit cfo.ai model | `01M4NZCR05WYB8MK3KFWWA8GEH` |
| [679ce33](https://github.com/Elena549-prog/Hackathon_neatlogs/commit/679ce33ae17be6d1070ccf38f650e3a25b3189da) | UI: dark brown theme | `01M4P4DWCS6Q3TCMMPZPK77MWS` |
| [3dd82ec](https://github.com/Elena549-prog/Hackathon_neatlogs/commit/3dd82ece3a5c92a548df4ad1c38664d1e5a13440) | UI: readable agent list, activity feed, replay matching | `01M4P725EADX0FTG0971SAX4CT` |

- The checkpoint data is on GitHub as `refs/entire/checkpoints/*` in this repo. The copies here are redacted and paraphrased.
- Repo on Entire: https://entire.io/gh/Elena549-prog/Hackathon_neatlogs. On 2026-10-12 the Sessions tab showed nothing while logged out; check it while logged in before citing it.
- Automatic session pushing (`push_sessions`) is off; these three checkpoints were pushed by hand.

## Not in the repo

- The demo video (`strategy-auditor-demo.mp4`, 5:00, 55 MB) is too big for git; share it separately. Its plan and numbers sheet: `docs/DEMO_VIDEO_PLAN.md`.
