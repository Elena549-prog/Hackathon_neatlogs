# Swarm summary: validation split

| Item | Value |
|---|---|
| Setups | 577 |
| Approved | 1 (0.2%) |
| Dropped after 2 rounds | 576 |
| Errors | 0 |
| LLM cost | $11.7572 |

## Precision of approved trades (share that hit +5% before -3%)

| Method | Approved | Precision |
|---|---|---|
| Swarm | 1 | 0.0% |
| Random, same approval rate (seed 0) | 1 | 0.0% |
| Always approve (= base rate) | 577 | 36.6% |

Mean P&L per approved trade: -3.0%.
Buy-and-hold over the split, mean across tickers: 2.2%.

Notes: no fees or slippage. Every plan uses the fixed +5%/-3%/10-day levels, so swarm
outcomes and labels score the same bet. Break-even precision is 37.5%.
Fewer than 50 approved trades: read as directional only.
