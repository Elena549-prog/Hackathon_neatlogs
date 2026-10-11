# Forward paper trading

Frozen swarm (commit f953747) on every trading day after the test split, prices through 2026-10-09. Paper trades only: +5% target, -3% stop, 10 trading days, no fees.

| Item | Value |
|---|---|
| Setups watched | 90 |
| Woken by the watcher | 7 |
| Approved (paper positions) | 0 |
| Errors | 0 |
| LLM cost | $0.2077 |

## Paper positions

None: the swarm declined every woken setup.

## Woken setups the swarm declined

| Date | Ticker | Reason |
|---|---|---|
| 2026-09-29 | AAPL | only 19 comparable past setups match the conditions; need at least 30 |
| 2026-09-25 | MSFT | cautious hit rate 28.2% (95% lower bound; plain 34.1% over 223 setups) is not above the 37.5% break-even |
| 2026-10-09 | MSFT | cautious hit rate 24.6% (95% lower bound; plain 32.0% over 128 setups) is not above the 37.5% break-even |
| 2026-09-23 | GOOGL | cautious hit rate 31.5% (95% lower bound; plain 39.8% over 118 setups) is not above the 37.5% break-even |
| 2026-10-08 | AMZN | cautious hit rate 28.5% (95% lower bound; plain 37.1% over 105 setups) is not above the 37.5% break-even |
| 2026-10-09 | AMZN | The edge is too thin to trust: the 95% lower-bound hit rate is 38.04%, only 0.54 percentage points above the 37.5% break-even, and the implied cautious EV is about 0.04% per trade before slippage/costs; this is not robust. |
| 2026-10-08 | NVDA | cautious hit rate 32.4% (95% lower bound; plain 37.8% over 291 setups) is not above the 37.5% break-even |
