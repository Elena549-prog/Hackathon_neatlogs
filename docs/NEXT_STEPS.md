# What to do next

Written 2026-10-11 after the step 5 validation run. Work through the sections in order. Owners are suggestions: Elena has the Kaggle setup for Laya; Zeeshan has the DeepSeek, neatlogs and cfo.ai accounts.

## Where we stand

| Done | Where |
|---|---|
| Steps 1–4: data, labels, splits, Laya export and fine-tune, baselines | `step-1-4` branch, `docs/HANDOVER.md` |
| Step 5: four-agent swarm, neatlogs tracing, paper-trade simulator | `swarm` branch, `src/` |
| Step 6 (swarm part): full validation run, 577 setups, 0 errors | `swarm` branch, `results/` |

**Validation result:** the swarm approved 1 of 577 setups (it lost 3%). Approving everything gives 36.6% precision, below the 37.5% break-even, and the baselines found no signal in the price features. Honest claim: *the swarm refuses to trade a market with no edge*. It does not show the swarm picks winners.

## Gaps against the judging criteria

| Criterion | Weight | Status | Fix in section |
|---|---|---|---|
| The agent | 30% | Works end to end on real data; result is "refuses to trade" | 3, 5 |
| Use of neatlogs, Entire, cfo.ai | 25% | neatlogs done. **Entire and cfo.ai not started** | 2, 4 |
| Demo video | 20% | Not started | 6 |
| Building in public | 15% | Nothing posted yet | 7 |
| Usefulness and originality | 10% | Story in section 6 | 6 |

The biggest cheap win is Entire and cfo.ai: 25% of the score, no model runs needed.

## 1. Housekeeping (Zeeshan, 15 min)

1. **Rotate the neatlogs API key.** The old SDK printed it in a run log, so treat it as exposed. Put the new one in `.env`.
2. **Delete `.env.txt` and `New Text Document.txt`** from the repo folder. `.env.txt` holds a key (it is gitignored, but should not exist).
3. **Merge PR #3** (swarm spec review) into `main`.
4. **Open a PR from `swarm` into `main`.** `docs/SWARM_SPEC.md` will differ from PR #3 in two places: the DeepSeek model table (section 3) and the leakage note (section 6). Keep both.

**Done when:** PR #3 is merged, the `swarm` PR is open, and `git status` shows no stray files.

## 2. Entire (Zeeshan, 30–45 min)

Entire records the context behind each AI-made change (prompt, transcript, tool calls, files) as a checkpoint linked to the commit. The hackathon wants it used to *build and improve* the agent, so every change from here on should go through it. Docs: https://docs.entire.io

1. Install (Windows PowerShell):
   ```powershell
   irm https://entire.io/install.ps1 | iex
   ```
   Check with `entire version`.
2. In the repo root, enable it for Claude Code:
   ```bash
   entire enable -y --agent claude-code
   ```
3. Add the code graph (local only, no network):
   ```bash
   entire plugin install graph
   ```
   ```bash
   entire graph init-agents --repo .
   ```
   `init-agents` adds managed blocks to `CLAUDE.md` and `AGENTS.md`. Review the diff before committing.
4. Make the next real change with Claude Code (section 5's test-run flag is a good first one), commit it, and answer `y` when Entire asks to link the commit to the session.
5. Check it: `entire checkpoint list`.

**Done when:** at least one commit on the branch has an Entire checkpoint. For the demo, pick a checkpoint where you can show the prompt and the resulting change side by side.

## 3. Laya validation scores and the go/no-go (Elena, 30–60 min)

This is the step `docs/HANDOVER.md` lists as next. Use Route A (Kaggle notebook) from the handover; it has the commands.

**Decision rule, written before the run:**
- If fine-tuned Laya's validation AUC has a 90% interval whose lower end is above 0.5, try the ensemble: per `docs/SWARM_SPEC.md` section 7, Laya's calibrated probability replaces `hit_rate_low` as p in the gate. Add that as a new spec section before coding it.
- Otherwise, use the plan's fallback (`docs/PLAN.md`): drop Laya from the accuracy claim, keep the swarm, and say so in the submission. Given the baselines (AUC 0.46–0.50), the fallback is the likely outcome.

**Done when:** the Laya rows are added to the baseline table in `docs/HANDOVER.md`, and the decision is written down with its numbers.

## 4. cfo.ai business plan (Zeeshan, 1 hour)

1. Sign up at cfo.ai/neathacks. **Cancel the subscription immediately** in Settings → Billing (rule from the hackathon page). The neatHack team provides credits.
2. Build the model from measured numbers, not guesses:

   | Input | Value | Source |
   |---|---|---|
   | LLM cost per decision | $0.038 upper bound (peak, cache-miss); about $0.019 off-peak | $11.76 over 310 setups, `results/README.md` |
   | Decisions per watchlist per month | 5 tickers × ~21 trading days = 105 | |
   | LLM cost per watchlist per month | ~$4.00 upper bound | 105 × $0.038 |
   | Laya inference | ~$0 marginal (runs locally or on a small GPU) | `docs/HANDOVER.md` |
   | neatlogs, hosting | fill in from your plans | |

3. Pricing hypothesis to model (change if you have a better one): a subscription per watchlist, e.g. $19/month, for a "pre-trade gate" that says no when the evidence isn't there. At ~$4 LLM cost that is roughly 79% gross margin before hosting.
4. Add base and growth scenarios, unit economics, and runway, as the hackathon page shows.
5. Export the plan for the submission.

**Done when:** the cfo.ai sheet computes cost per customer and margin from formulas, and the export is in the repo (for example `results/business_plan.pdf`).

## 5. One-shot test evaluation (after section 3)

The plan touches the test split exactly once, with a frozen configuration.

1. Freeze the configuration: swarm alone (fallback) or swarm plus Laya (if section 3 passed). Write it in `results/README.md` first.
2. `src/swarm.py` refuses `--split test` on purpose. Add an explicit flag (for example `--final-test`) that allows one run and refuses to overwrite an existing test result. Do this change under Entire (section 2).
3. Run it once: 231 setups, about $9 upper bound, about 35 minutes at 8 workers.
   ```bash
   .venv/Scripts/python.exe -m src.swarm --split test --final-test --workers 8
   ```
4. Copy the summary and decision log into `results/` like the validation run. Do not change anything after seeing the result.

**Done when:** `results/` has the test summary and the README states the frozen config and the outcome, good or bad.

## 6. Demo video (both, 1–2 hours)

About 3 minutes. Suggested beats:

1. **Problem (20 s):** trading agents report confident wins they can't back up.
2. **The swarm (40 s):** Researcher, Planner, Mathematician, Naysayer; agents see anonymized data; fixed +5%/−3% bet.
3. **A trace in neatlogs (40 s):** open one of the 25 setups where the Naysayer blocked a plan that passed the gate. Show the plan, the backtest numbers, the objection.
4. **The result (30 s):** 1 of 577 approved; approving everything loses (36.6% < 37.5%). The agent's value is saying no.
5. **Entire (20 s):** a checkpoint showing the prompt behind a code change.
6. **cfo.ai (20 s):** cost per decision, pricing, margin.
7. **Honest close (10 s):** what Laya did or didn't add; the test-split result.

## 7. Building in public (Zeeshan, ongoing)

Post 2–3 times before the deadline, each with one concrete artifact:
- "Our trading agent refused 576 of 577 trades, and that's the right answer" (neatlogs trace screenshot).
- "How a Naysayer agent blocks a plan that looks good on paper" (one trace, plan vs objection).
- "What a trading agent costs to run: $0.04 per decision" (cfo.ai screenshot).

## Do not

- Don't tune the gate, prompts, or thresholds on the validation results to get more approvals. That turns validation into training data and invalidates the test run.
- Don't run the test split more than once.
- Don't re-run full validation for small changes; it costs about $20. Use `--limit` for checks.
- Don't commit `.env`, keys, `data/`, or `runs/`. Results go in `results/`.
