# Building the business plan in cfo.ai

The model is ready as an Excel workbook: `results/business_model.xlsx`. cfo.ai's assistant, Ari, can import a workbook and rebuild it as a native cfo.ai model, turning the assumptions into Variables and the two cases into Scenarios (cfo.ai docs: "Import a spreadsheet model").

## What's in the workbook

| Sheet | Contents |
|---|---|
| Summary | 24-month results for both scenarios: customers, MRR, gross margin, operating profit, lowest cash, runway, break-even, funding need, LTV:CAC |
| Assumptions | Every input with its source. Blue = input, yellow = owner estimate to confirm. Column B = Base, column C = Growth |
| Model_Base, Model_Growth | Monthly model: customers, revenue, payment fees, LLM and Laya cost, gross profit, marketing, fixed costs, operating profit, cash |
| Unit_Economics | One watchlist per month: contribution margin, CAC payback, LTV, LTV:CAC |

Every output is a formula; there are no typed-in results. All 1,010 formulas were evaluated (with pycel) and checked against an independent Python calculation of the same model; they match. The file has no cached values, because it was written by a script: Excel computes them when it opens the file, and Ari reads the formulas.

## Measured vs assumed

- **Measured:** LLM cost per decision, $0.038 (upper bound at DeepSeek peak prices, from the validation run in `results/README.md`, which used two Planner rounds per setup; the conditional second round should lower it). Watcher share of days, 12.3% (train split).
- **Standard pricing:** card fees, 2.9% + $0.30 (Stripe US).
- **Owner estimates (yellow):** price ($19 per watchlist per month), new customers, growth, churn, CAC, hosting, neatlogs, team cost, starting cash. Change them before presenting the plan if you have better numbers.

## Results with the current assumptions

| | Base | Growth |
|---|---|---|
| Customers, month 24 | 238 | 1,504 |
| MRR, month 24 | $4,516 | $28,569 |
| Contribution margin per watchlist | $17.66 (93%) | $17.66 (93%) |
| LTV to CAC | 7.4x | 7.4x |
| Break-even month | 17 | 15 |
| Lowest cash balance | $6,538 | −$28,519 |
| Funding needed to never go below zero | $0 | $28,519 |

Reading: the price watcher (section 15 of `docs/SWARM_SPEC.md`) wakes the swarm on about 12% of days, so a watchlist costs about $0.49 a month in LLM calls instead of $3.99. Base survives on $25,000. Growth needs about $28,500 of outside funding before it breaks even in month 15.

Before the watcher, the same model gave $14.16 (74.5%) contribution margin, 5.9x LTV:CAC, and a $43,130 funding need for Growth.

## Steps (Zeeshan)

1. Sign up at cfo.ai/neathacks. **Cancel the subscription immediately** in Settings → Billing, as the hackathon page instructs. The neatHack team provides credits.
2. Optional: open `results/business_model.xlsx` in Excel, change any yellow assumption, and save. Saving in Excel also stores the computed values.
3. Start a conversation with Ari, attach the workbook, and paste:

   > Import this workbook into cfo.ai as a native Model. It is a 24-month plan for a subscription product priced per watchlist. Make every input on the Assumptions sheet a Variable. Make column B (Base) the Main scenario and column C (Growth) a second Scenario. Keep the monthly time grain starting at month 1, with no Actuals.

4. Check the rebuild, paste:

   > Reconcile the rebuilt revenue, gross profit, operating profit and ending cash to the attached workbook for months 12 and 24 in both scenarios, and list any differences.

5. Ask Ari for the runway view and a short plan summary:

   > Show runway and the funding needed for each scenario, and draft a one-page business plan summary from this Model.

6. Share the model or page as a read-only link and put the link, plus a screenshot, in the submission. Save a PDF or screenshots to `results/` too.

**Done when:** the Model has both Scenarios, the reconciliation shows no differences, and the share link is in the submission.
