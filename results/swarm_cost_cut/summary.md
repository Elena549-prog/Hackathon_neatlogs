# Swarm summary: validation split

| Item | Value |
|---|---|
| Setups | 30 |
| Watcher woke the swarm (1-day move at least 1.5 x 20-day vol) | 8 (26.7%) |
| Skipped by the watcher (no LLM call) | 22 |
| Approved | 0 (0.0% of woken) |
| Dropped | 8 |
| Errors | 0 |
| LLM cost | $0.1972 ($0.0247 per woken setup) |

## Precision of approved trades (share that hit +5% before -3%)

| Method | Approved | Precision |
|---|---|---|
| Swarm | 0 | n/a |
| Random, same approval rate among woken setups (seed 0) | 0 | n/a |
| Always approve woken setups | 8 | 37.5% |
| Always approve every setup (= base rate) | 30 | 36.7% |

Mean P&L per approved trade: n/a.
Buy-and-hold over the split, mean across tickers: 2.2%.

Notes: no fees or slippage. Every plan uses the fixed +5%/-3%/10-day levels, so swarm
outcomes and labels score the same bet. Break-even precision is 37.5%.
Fewer than 50 approved trades: read as directional only.
