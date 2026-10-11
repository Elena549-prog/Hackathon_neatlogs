# Demo video plan (about 3 minutes)

Built from four real recordings of mission control plus three dashboard captures still to make. Every number below comes from a file in `results/` or a neatlogs trace; the source is listed in the numbers sheet at the end. Spec beats (AUDITOR_SPEC section 13): idea → agents at work → a recovery (labelled) → verdict → neatlogs trace → Entire checkpoint → cfo.ai plan → before/after.

## Assets

### Recorded (1920×1080, 30 fps, mission control replaying real runs at 1×, gaps over 2 s capped)

| File | Length | Run | Ends on |
|---|---|---|---|
| `demo-video/clips/dips.mp4` | 17.1 s | `after-dips`: "buy dips in an uptrend", M2 with follow-ups | INCONCLUSIVE |
| `demo-video/clips/straddle-buy-fault.mp4` | 17.5 s | `fault-dolthub`: "buy straddles on tech before earnings", DoltHub timeout injected | KILLED |
| `demo-video/clips/straddle-sell.mp4` | 15.5 s | `after-straddle-sell`: "sell straddles on low-volatility mega-caps" | KILLED |
| `demo-video/amzn-trade-mission-control.mp4` | 22.2 s | `trade-amzn-2026-07-30`: swarm trade decision, Naysayer v1 vs v2 | APPROVED · PAPER TRADE |

Key moments inside each clip (seconds from the start of the file; computed from the event files, ±0.5 s):

| Clip | Moment |
|---|---|
| dips | 1.5 Planner starts · 3.5 Researcher · 6.1 equity curves draw · **8.1 Naysayer asks for follow-ups F1, F3, F4** · **11.6 INCONCLUSIVE stamp** · 17.1 end |
| straddle-buy-fault | 1.5 Planner · **3.9 "↺ injected" badge + "recovered (INJECTED): DoltHub timeout … retried after 2 s" in the feed** · 6.9 checks land (decay, cost realism FAIL) · **11.0 KILLED stamp** · 17.5 end |
| straddle-sell | 1.5 Planner · **4.6 three FAIL cards (decay, cost realism, tail risk)** · **8.6 KILLED stamp** · 15.5 end |
| amzn-trade | 3.5 Researcher · 5.9 Planner · 7.7 past matches + setup chart · 8.9 Naysayer starts · **11.3 Naysayer v1 FAIL card** · 13.3 live LLM call · **~14 Naysayer v2 PASS** · 15.1 chart extends to the next day (+15.3%) · **15.7 APPROVED · PAPER TRADE, +5.00%** · 22.2 end |

Re-record any clip with mission control running (`.venv/Scripts/python.exe -m uvicorn src.auditor.server:app --port 8000`) and the recorder in the session scratchpad (`node record.mjs "<chip text>" out.mp4 1 6`), or screen-record http://127.0.0.1:8000/ yourself: click the chip, speed 1×.

### Still to capture (needs your logins)

| Asset | What to show | How |
|---|---|---|
| neatlogs trace, dips audit | Trace `66f9d2d4745323068e43c84d01c9bad1`: span tree (planner → researcher tools → mathematician → naysayer), LLM spans with tokens and cost ($0.0114 in total) | neatlogs dashboard, project "Zeeshan's project", workflow `trading-swarm`; open the trace, expand the naysayer span. 8–10 s screen recording |
| neatlogs trace, AMZN decision | Trace `7b8501eaf5cdfa8d7918338e5a2e4cc0` (tag `naysayer-replay`): the live Naysayer v2 call | Same; optional, use if the dips trace is too busy |
| Entire checkpoint | A checkpoint linked to a commit: the prompt and the code change side by side | Three commits on `main` carry `Entire-Checkpoint` trailers: `92918c8` (M2 follow-ups, `01M4NZCR05WYB8MK3KFWWA8GEH`), `679ce33` (brown theme, `01M4P4DWCS6Q3TCMMPZPK77MWS`), `3dd82ec` (UI readability, `01M4P725EADX0FTG0971SAX4CT`). The session data sits on the local branch `entire/67bdece-e3b0c4` only: `push_sessions` is false (kept off until the neatlogs key is rotated), so nothing is on Entire's side yet. Rotate the key, set `push_sessions` to true, push, then record `3dd82ec`'s checkpoint |
| cfo.ai model | Summary page (Base vs Growth side by side), then the Assumptions page with the $0.0085 cost cell | Built (docs/CFO_AI.md). Record the Summary page, then change `LLM cost per audit` to 0.0351 on camera to show everything recalculate, and change it back |
| Before/after card | The M1 vs M2 table | Made in the edit from `results/audits/before_after.md` (no capture needed) |

Voiceover: record after the cut is locked, about 150 words per minute. No music is required; if wanted, a quiet bed under −20 dB.

## Beat sheet

| # | Time | Picture | On-screen text | Voiceover |
|---|---|---|---|---|
| 1 | 0:00–0:12 | Black, then mission control idle (first 1.5 s of `dips.mp4`, frozen) | "Most trading bots show you their wins." → "Ours has to prove the edge first." | "Trading bots love to show you their wins. We built one that has to prove its edge on data it has never seen, or it says no." |
| 2 | 0:12–0:30 | Same frame; light callouts on the four agent rows and the three panels | "Planner · Researcher · Mathematician · Naysayer" | "You type a strategy in plain English. A Planner turns it into a precise, frozen test. A Researcher pulls the data. A Mathematician backtests it in code, not with an LLM. And a Naysayer tries to break it. The verdict rules are code; the LLMs explain, they can't overrule." |
| 3 | 0:30–0:55 | `dips.mp4` 1.5 → 17.1 at 1×. Zoom on the Objections panel at 8.1 (follow-ups). Freeze 2 s on the stamp at 11.6 | "buy dips in an uptrend" | "First idea: buy dips in an uptrend. The agents plan it, pull twelve years of prices for fifty stocks, and backtest it. The Naysayer isn't convinced, so it orders three extra tests: without earnings, other horizons, without the best stock. Verdict: inconclusive. Plus one percent a trade on paper, but the lower bound is below zero. No edge we can trust." |
| 4 | 0:55–1:20 | `straddle-buy-fault.mp4` 1.5 → 13.0. Zoom on the "↺ injected" badge and the feed line at 3.9, hold 2 s. Freeze 2 s on KILLED at 11.0 | "Failure injected on purpose" | "Second idea: buy straddles on tech before earnings. Here we injected a failure: the options data source times out. The Researcher catches it, retries, labels it as injected, and the audit carries on. Verdict: killed. Minus eighteen percent per trade on data it never trained on." |
| 5 | 1:20–1:35 | `straddle-sell.mp4` 3.5 → 11.0. Zoom on the three FAIL cards at 4.6. Freeze on KILLED at 8.6 | "sell straddles on low-volatility mega-caps" | "Third: sell straddles on quiet mega-caps. It looks like free money until the tail-risk check fires: one bad trade lost more than four times the premium it collected. Killed." |
| 6 | 1:35–1:50 | Card: before/after table (below) | "Before vs after the Naysayer's follow-ups" | "We improved the Naysayer by letting it order follow-up tests. Same three ideas, before and after. The verdicts held, and each audit costs about a cent." |
| 7 | 1:50–2:22 | `amzn-trade-mission-control.mp4` 1.5 → 22.2. Zoom on the Objections panel 11.3 → 15.0 (v1 FAIL, then v2 PASS). Hold the APPROVED stamp to the end | "AMZN, 30 Jul 2026" | "The same agents also make single trade decisions. Our first Naysayer was too strict: the trades it vetoed would have won more than they lost. We rewrote its rules and replayed a trade it had blocked. The old Naysayer said no. The new one approved it, and the next day the target hit: plus five percent." |
| 8 | 2:22–2:35 | neatlogs trace recording (dips or AMZN) | "Every step traced in neatlogs" | "Every agent step, tool call and token is traced in neatlogs, so you can see exactly why each decision was made." |
| 9 | 2:35–2:45 | Entire checkpoint recording | "Built with Entire" | "We built it with Claude Code and Entire, so every change keeps the prompt and the reasoning behind it." |
| 10 | 2:45–2:55 | cfo.ai sheet recording | "About a cent per audit" | "And it's cheap: about a cent per audit in measured LLM cost, so a per-audit price leaves a wide margin." |
| 11 | 2:55–3:00 | Mission control, final frame of the AMZN clip | "Prove the edge, or don't trade. #neatHack" | "Prove the edge, or don't trade." |

Script length: about 400 words, about 2:45 of speech, leaving room for the holds.

### Before/after card (beat 6)

From `results/audits/before_after.md`:

| Idea | Before (M1) | After (M2, follow-ups) | Cost before → after |
|---|---|---|---|
| buy dips in an uptrend | inconclusive | inconclusive (F1, F3, F4 run; no rule met) | $0.023 → $0.047 |
| tech straddles before earnings | kill | kill | $0.017 → $0.022 |
| short straddles, low-vol mega-caps | kill | kill | $0.016 → $0.037 |

Costs on the card are the wrapper's upper bound (peak, cache-miss prices). Say "about a cent" only with the neatlogs figures (numbers sheet).

## Edit notes

- Keep the clips at 1×; the replays already cap waits at 2 s. Use freeze frames and zooms, not speed-ups, so the text stays readable.
- Zoom targets are fixed by the layout: agents (left third), Evidence (middle), Objections (right third), verdict stamp (bottom band).
- The clips' own top bar shows "REPLAY · date", which is accurate; leave it.
- Cut on stamps: each audit beat ends on its verdict stamp with a 2 s hold.
- Tool options: assemble it in HyperFrames (clips as video tracks, title cards and the before/after card as HTML, captions from the script), or in Clipchamp or DaVinci Resolve.

## Numbers sheet

| Number | Value | Source |
|---|---|---|
| Dips verdict and figures | inconclusive, validation n 303, mean +0.96%, lower bound −0.25% | `results/audits/after-dips/report.md` |
| Tech straddles | kill, validation mean −18.38% over 34 trades | `results/audits/fault-dolthub/report.md` |
| Injected recovery | DoltHub timeout on window 2026-06-17..2026-06-30, retried after 2 s, labelled INJECTED | `results/audits/fault-dolthub/report.md` section 8 |
| Short straddles | kill, validation n 70, mean −10.18%; worst trade −437.80% (−5.9 average premiums) | `results/audits/after-straddle-sell/report.md` |
| Before/after | table above | `results/audits/before_after.md` |
| Cost per audit, neatlogs (actual) | $0.0114, $0.0056, $0.0085: mean **$0.0085** | neatlogs traces of the three after-audits |
| Cost per audit, wrapper (upper bound) | mean **$0.0351** | `cost.usd` in each after-audit `state.json` |
| cfo.ai cost cell | $0.0085 measured (Base: 94% gross margin per paid audit, month-12 cash $2,193; Growth: cash below zero in month 4, needs $47,346) | cfo.ai workspace "Zeeshan CFOAI", docs/CFO_AI.md |
| AMZN decision | 39 of 1,263 past setups, hit rate 59.0%, cautious 43.4% vs 37.5% break-even; v1 block; v2 approve; long 283 at $235.50, stop $228.44, target $247.28; next close $271.58; +5.00% (+$3,332 on paper) | `results/posthoc_amzn_v1_naysayer.json`, `results/audits/trade-amzn-2026-07-30/events.jsonl` |
| "trades it vetoed would have won more than they lost" | on validation, v1's blocks of gate-passing plans would have won 16 of 38 (42.1%, above 37.5%) | `results/README.md` |

Context the voiceover leaves out, for the write-up and Q&A: the AMZN setup is from the test window already seen, and Naysayer v2 was written after that run (`results/README.md`, "Naysayer v2: post-hoc replay"). With v1 the swarm took no trades on the locked test window (0 of 231) or on live forward days (0 of 90).

## Checklist

- [ ] Entire: push the session data for the three linked commits (`push_sessions` true after the key rotation)
- [x] cfo.ai: model built natively, reconciled to the workbook, measured cost set
- [ ] cfo.ai: share link for the submission (pages are private until then)
- [ ] neatlogs: rotate the old API key (STATUS), then record the trace beat
- [ ] Record the voiceover against the locked cut
- [ ] Final check: every on-screen number matches the numbers sheet
