# Swarm summary: validation split

| Item | Value |
|---|---|
| Setups | 577 |
| Watcher woke the swarm (1-day move at least 1.5 x 20-day vol) | 98 (17.0%) |
| Skipped by the watcher (no LLM call) | 479 |
| Approved | 0 (0.0% of woken) |
| Dropped | 98 |
| Errors | 0 |
| LLM cost | $2.8658 ($0.0292 per woken setup) |

## Precision of approved trades (share that hit +5% before -3%)

| Method | Approved | Precision |
|---|---|---|
| Swarm | 0 | n/a |
| Random, same approval rate among woken setups (seed 0) | 0 | n/a |
| Always approve woken setups | 98 | 43.9% |
| Always approve every setup (= base rate) | 577 | 36.6% |

Mean P&L per approved trade: n/a.
Buy-and-hold over the split, mean across tickers: 2.2%.

Notes: no fees or slippage. Every plan uses the fixed +5%/-3%/10-day levels, so swarm
outcomes and labels score the same bet. Break-even precision is 37.5%.
Fewer than 50 approved trades: read as directional only.
