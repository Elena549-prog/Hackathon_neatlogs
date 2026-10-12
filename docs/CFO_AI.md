# Building the business plan in cfo.ai

**Built in cfo.ai on 2026-10-12** (workspace "Zeeshan CFOAI"), as a native model rather than an upload: pages Assumptions (20 editable inputs), Monthly model (25 lines, Nov 2026 to Oct 2027, last close Oct 2026 holding the opening users and cash), Unit economics and Summary, with Main Scenario as Base and a Growth scenario that overrides only its five levers. Every Model_Base, Model_Growth, Unit_Economics and Summary figure checked (months 1, 6, 12, the 12-month totals, runway and funding) matched the workbook to the cent at the workbook's $0.048 cost. The cost cell was then set to the **measured $0.0085 per audit** (mean neatlogs cost of the three after-audits; the wrapper's upper bound is $0.0351): Base 12-month LLM cost $202.19 → $35.80 and month-12 cash $2,026.83 → $2,193.21, revenue unchanged. Cost_Estimate is superseded by the measurement and was not rebuilt; the Assumptions page says so. Read-only share links (anonymous visitors allowed, all four pages): **Base** https://app.cfo.ai/s/3gz1yhzF4-VhA24I and **Growth** https://app.cfo.ai/s/wSxyktuJXgE93MQJ. A link grants one scenario, so guests see one column per link; workspace members see Base and Growth side by side on the Summary page.

The model is an Excel workbook, `results/business_model.xlsx`, priced **per audit** (AUDITOR_SPEC section 13): one audit = one trading idea in, one evidence-backed verdict out. cfo.ai's assistant, Ari, can import a workbook and rebuild it as a native cfo.ai model, turning the assumptions into Variables and the two cases into Scenarios (cfo.ai docs: "Import a spreadsheet model").

Rebuild it with `python scripts/spikes/build_business_model.py results/business_model.xlsx`; check it with `python scripts/spikes/verify_model.py results/business_model.xlsx`.

## The single cost variable

**`Assumptions!B5`, "LLM cost per audit (USD)" = $0.0085, MEASURED.** The mean neatlogs cost of the three M2 after-audits ($0.0114, $0.0056, $0.0085; `docs/SUBMISSION.md`). Every LLM cost in the model is a formula on this one cell, in both scenarios. The same value is in the cfo.ai Variable, and the workbook matches the live model to the cent.

Before any real DeepSeek audit had run, it was estimated bottom-up from the code on the `Cost_Estimate` sheet, which the workbook keeps as documentation:

| Call (spec section 4, at M2) | Model | Calls per audit | Prompt tokens | Completion tokens | $ per call |
|---|---|---|---|---|---|
| Planner: idea to plan v0 | deepseek-v4-pro, thinking | 1 | 1,220 | 3,000 | 0.0135 |
| Planner: fix after an invalid plan | deepseek-v4-pro, thinking | 0.1 (10% chance) | 1,280 | 3,000 | 0.0136 |
| Naysayer 1: doubts, choose follow-ups | deepseek-v4-pro, thinking | 1 | 1,280 | 3,000 | 0.0136 |
| Naysayer 2: final critique | deepseek-v4-pro, thinking | 1 | 1,360 | 3,000 | 0.0137 |
| Reporter: prose | deepseek-flash, no thinking | 1 | 2,670 | 300 | 0.0012 |
| **Total** | | **4.1** (budget 8) | | | **0.0433** |

Plus 10% for retries (billed, spec section 8): **$0.0476 per audit**, typed as $0.048 until M2. The measured $0.0085 is 5.6x lower.

- Prices: `src/llm.py` `PRICES`, DeepSeek peak cache-miss ($1.32 / $3.96 per 1M tokens for v4-pro, $0.30 / $1.20 for flash), so it is an upper bound. Off-peak is half: $0.024.
- Prompt tokens = characters / 4. System prompts (including the M2 follow-up prompt, `NAYSAYER_FOLLOWUPS_SYSTEM`) are read from `src/auditor/agents.py` at build time, plus the JSON-schema suffix `src/llm.py` appends. User prompts were measured by running the audit loop with the fake LLM on a synthetic 50-ticker market for the three demo ideas, then rounded up.
- Completion tokens: 3,000 per thinking call (thinking + JSON reply) is an assumption; the plausible range is 1,500 to 4,000.
- Sanity check: the swarm measured $0.038 per decision with two v4-pro thinking calls (`results/README.md`), about $0.019 per thinking call. At that rate an audit (3.1 thinking calls + Reporter) costs about $0.060. The bottom-up estimate is 0.8x of that: the same few cents.
- Worst case, all 8 budgeted calls: $0.105 per audit.
- Data costs $0 (Yahoo Finance, DoltHub public data). Hosting is a fixed $50 a month (one small VM), not a per-audit cost.

**Measured after M2 (done 2026-10-12):** the mean neatlogs cost of the three M2 after-audits, $0.0085, is in `Assumptions!B5` and in the cfo.ai Variable. The wrapper's `cost.usd` in each `state.json` uses peak cache-miss prices, so it is an upper bound (mean $0.0351). M1 runs make one Naysayer call, not two, so they were left out. To change it again, edit `LLM_INPUT` in `build_business_model.py` and rebuild, and change the cfo.ai Variable. Everything downstream recalculates.

## What's in the workbook

| Sheet | Contents |
|---|---|
| Summary | 12-month results for both scenarios: cost and margin per audit and per subscriber, LTV:CAC, users, audits, revenue, operating profit, lowest cash, runway, break-even, funding need |
| Assumptions | The cost variable (B5), then every other input with its source. Blue = input, yellow = estimate or hypothesis to confirm. Column B = Base, column C = Growth |
| Cost_Estimate | How B5 was estimated: prices, token assumptions, per-call table, swarm sanity check |
| Model_Base, Model_Growth | Monthly model: users (subscribers and pay-per-audit), audits, revenue by plan, payment fees, LLM, data, gross profit, marketing, fixed costs, operating profit, cash |
| Unit_Economics | One audit (pay per audit), one subscriber per month, blended user: contribution, gross margin, CAC payback, LTV, LTV:CAC |

All 763 formulas evaluate without errors (pycel), and the key outputs match an independent Python calculation of the same model. The file has no cached values, because it was written by a script: Excel computes them when it opens the file, and Ari reads the formulas.

## Pricing hypotheses and other inputs

- **Hypotheses (yellow):** $2 per audit, sold in packs of 5 (one card charge per $10 pack, so Stripe's $0.30 fee takes 3% instead of 15%); a hobbyist plan at $15 a month for 20 audits. 40% of users on the plan, running 10 audits a month; pay-per-audit users run 3.
- **Owner estimates (yellow):** new users, growth, churn, CAC, team cost, starting cash ($25,000), hosting. Change them before presenting if you have better numbers.
- **Standard pricing:** card fees, 2.9% + $0.30 (Stripe US).

## Results at the measured $0.0085 per audit

Same figures in the live cfo.ai model and in the workbook (`verify_model.py`: all checks pass).

| | Base | Growth |
|---|---|---|
| Contribution per audit (pay per audit) | $1.87 (93.7%) | $1.87 (93.7%) |
| Contribution per subscriber per month | $14.18 (94.5%) | $14.18 (94.5%) |
| LTV to CAC | 3.8x | 3.8x |
| Paying users, month 12 | 110 | 416 |
| Revenue, month 12 | $1,055 | $3,994 |
| LLM cost, months 1-12 | $35.80 (was $202.19 at the $0.048 estimate) | $117.95 |
| Operating profit, months 1-12 | −$22,807 | −$72,346 |
| Cash, end of month 12 | $2,193 (about 1.4 months left) | −$47,346 (below zero in month 4) |
| Funding needed to never go below zero | $0 | $47,346 |

Reading: at under a cent an audit, LLM cost is 0.4% of the $2 price; card fees ($0.118 an audit) cost 14x more. The cost per audit would have to reach $1.88, about 220x the measured cost, before an audit stops contributing. The plan is decided by users, churn, CAC and team cost, not by inference. Neither scenario breaks even within 12 months on these owner estimates.

## Steps (Zeeshan)

1. Sign up at cfo.ai/neathacks. **Cancel the subscription immediately** in Settings → Billing, as the hackathon page instructs. The neatHack team provides credits.
2. Optional: open `results/business_model.xlsx` in Excel, change any yellow input, and save. Saving in Excel also stores the computed values.
3. Start a conversation with Ari, attach the workbook, and paste:

   > Import this workbook into cfo.ai as a native Model. It is a 12-month plan for the Strategy Auditor, a research tool priced per audit: pay per audit, or a hobbyist plan with a monthly allowance of audits. Make every input on the Assumptions sheet a Variable. Name the Variable from cell B5 "LLM cost per audit (USD)", keep it as one Variable shared by both scenarios, and label it ESTIMATE, with the note from cell E5. Make column B (Base) the Main scenario and column C (Growth) a second Scenario. Keep the monthly time grain starting at month 1, with no Actuals. Keep the Cost_Estimate sheet as documentation of how the estimate was built.

4. Check the rebuild, paste:

   > Reconcile the rebuilt revenue, LLM cost, gross profit, operating profit and ending cash to the attached workbook for months 6 and 12 in both scenarios, and the Unit_Economics contribution per audit and per subscriber, and list any differences.

5. Ask Ari for the per-audit view, the runway, and a short plan summary:

   > Show unit economics per audit and per subscriber, runway and the funding needed for each scenario, and how gross margin per audit changes if LLM cost per audit is 2x and 5x the estimate. Then draft a one-page business plan summary from this Model, stating that LLM cost per audit is an estimate until it is measured.

6. Share the model or page as a read-only link and put the link, plus a screenshot, in the submission. Save a PDF or screenshots to `results/` too.
7. Done 2026-10-12. After M2: replace the cost Variable with the measured figure (see "The single cost variable" above) and ask Ari:

   > Update the Variable "LLM cost per audit (USD)" to <measured value>, measured from <n> real audits (neatlogs and the reports' cost sections). Remove the ESTIMATE label, note the source, and show what changed in the summary.

**Done when:** the Model has both Scenarios and the single cost Variable, the reconciliation shows no differences, the share link is in the submission, and after M2 the cost Variable holds the measured figure.
