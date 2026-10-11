# Demo prep (NEXT_STEPS section 6)

Draft for the ~3-minute demo video. All numbers come from `results/` (validation split) and `docs/HANDOVER.md`. The test-split result and the Laya decision are still open; fill those beats in last.

## Trace to show in neatlogs (beat 3)

Setups where the plan **passed the numbers gate** but the **Naysayer blocked it** with its own reasoning. Find them in the `trading-swarm` workflow by the `ticker` and `date` span tags. All three would have lost (label 0), which makes the point visually, but see the caution below.

| Setup | Plan's thesis (short) | Naysayer's key objection |
|---|---|---|
| **AAPL 2026-06-16** (first choice) | Pullback in a long-term uptrend: above the 200-day average, 10-day return negative | The stock had already bounced: +3.0% over 5 days and +1.0% that day, so the "pullback" entry chases the rebound. Above the 200-day average alone doesn't prove an uptrend |
| AAPL 2026-06-10 | Short pullback while still above the 50-day average | Today's 5-day drop (−6.0%) is far deeper than the −2% condition, so the matched history (mostly mild dips) doesn't describe this case |
| AAPL 2026-02-20 | Buyable dip above the 200-day average | Price above the 200-day average doesn't mean the average is rising; and the edge (lower bound 43.1% vs 37.5% break-even) is too thin to trust |

What to show, in order: the plan JSON (thesis and conditions), the Mathematician's numbers (matching setups, cautious hit rate, expected value), then the Naysayer's objections.

**Caution:** the Naysayer also blocked some plans that would have won (for example several MSFT setups in May 2026). Present it as "a skeptic that checks whether the thesis matches the data", not "the Naysayer is always right".

## Voiceover draft

**1. Problem (20 s).** "Trading bots love to report wins. Most can't show those wins hold up on data they've never seen. We built one that has to prove its edge, or it doesn't trade."

**2. The swarm (40 s).** "Four agents debate every setup. A Researcher reads the price data, a Planner proposes a trade and the conditions behind it, a Mathematician checks those conditions against past data, and a Naysayer tries to break the plan. Every trade is the same bet: plus 5 percent before minus 3 percent within 10 days. The agents never see the ticker or the date, so they can't lean on what they remember about the market."

**3. A trace in neatlogs (40 s).** Show AAPL 2026-06-16. "Here the plan passed the numbers check. But the Naysayer noticed the stock had already bounced 3 percent, so the 'buy the dip' entry was chasing the rebound. Blocked. Every step is traced in neatlogs, so we can see exactly why."

**4. The result (30 s).** "We ran 577 historical setups from the first half of 2026. The swarm approved one. That sounds like a failure, but if you'd approved everything, only 36.6 percent hit the target, below the 37.5 percent you need to break even. There was no edge in the price data, and three standard ML models agree: none beat a coin flip. The swarm's value is saying no."

**5. Entire (20 s).** Show a checkpoint: the prompt and the resulting code change side by side. *(Pending: Entire setup.)*

**6. cfo.ai (20 s).** "Running it costs about 4 cents per decision. As a subscription per watchlist, that's a healthy margin." *(Pending: cfo.ai sheet; check the numbers against NEXT_STEPS section 4.)*

**7. Honest close (10 s).** *(Pending: Laya go/no-go and the one-time test run.)* Template: "We fine-tuned Laya as a fast second opinion; on unseen data it [did / did not] beat a coin flip, so we [kept it / left it out]. On the locked test period the swarm [result]."

## Visuals already made
- Architecture diagram (swarm, Laya, ensemble, tools): posted with update #1.
- "577 setups debated, 1 trade approved" chart with the drop reasons: posted with update #2.

## Checklist before recording
- [ ] Laya decision written in `docs/HANDOVER.md` (NEXT_STEPS section 3)
- [ ] Test run done once, result in `results/` (section 5)
- [ ] Entire checkpoint to show (section 2)
- [ ] cfo.ai sheet exported (section 4)
- [ ] neatlogs: AAPL 2026-06-16 trace opened and checked
