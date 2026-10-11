# Strategy Auditor report: KILLED

straddle_buy on tech (17 tickers): enter when earnings_within_10d > 0; hold 10 days. Not tested: Specific strike selection and option pricing/greeks; Transaction costs and bid-ask spreads; Directional earnings surprise.

## 1. What was tested and the verdict

**Verdict: KILLED.** validation mean <= 0 with enough evidence

Headline: validation n = 34, mean per trade -18.38%, lower bound -36.18%, paired lower bound vs baseline -31.73%.

## 2. Idea, plan v0, assumptions

Idea: buy straddles on tech before earnings

Plan v0 (frozen before any backtest), SHA-256 `0e7bf7eafed88363a6a9c972dcfeab78673fbce1776c1d66afe694d0c2247698`:

```json
{
  "assumptions": [
    "'before earnings' read as an earnings report falls within the next 10 trading days",
    "Straddle is at-the-money and held for 10 days"
  ],
  "conditions": {
    "earnings_within_10d": [
      ">",
      0
    ]
  },
  "core_trigger_tested": true,
  "family": "straddle_buy",
  "hypothesis": "Buying at-the-money straddles on tech stocks before earnings captures volatility expansion around earnings announcements.",
  "not_tested": [
    "Specific strike selection and option pricing/greeks",
    "Transaction costs and bid-ask spreads",
    "Directional earnings surprise"
  ],
  "refused": false,
  "universe_group": "tech"
}
```

Assumptions: 'before earnings' read as an earnings report falls within the next 10 trading days; Straddle is at-the-money and held for 10 days.
Not tested: Specific strike selection and option pricing/greeks; Transaction costs and bid-ask spreads; Directional earnings surprise.
Universe: tech = AAPL, MSFT, NVDA, AVGO, CSCO, CRM, ACN, ADBE, TXN, AMD, INTC, QCOM, IBM, GOOGL, META, NFLX, DIS.

## 3. Data coverage

| Ticker | 2014 | 2015 | 2016 | 2017 | 2018 | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| AAPL | 252 | 252 | 252 | 251 | 251 | 252 | 253 | 252 | 251 | 250 | 252 | 250 | 143 |
| MSFT | 252 | 252 | 252 | 251 | 251 | 252 | 253 | 252 | 251 | 250 | 252 | 250 | 143 |
| NVDA | 252 | 252 | 252 | 251 | 251 | 252 | 253 | 252 | 251 | 250 | 252 | 250 | 143 |
| AVGO | 252 | 252 | 252 | 251 | 251 | 252 | 253 | 252 | 251 | 250 | 252 | 250 | 143 |
| CSCO | 252 | 252 | 252 | 251 | 251 | 252 | 253 | 252 | 251 | 250 | 252 | 250 | 143 |
| CRM | 252 | 252 | 252 | 251 | 251 | 252 | 253 | 252 | 251 | 250 | 252 | 250 | 143 |
| ACN | 252 | 252 | 252 | 251 | 251 | 252 | 253 | 252 | 251 | 250 | 252 | 250 | 143 |
| ADBE | 252 | 252 | 252 | 251 | 251 | 252 | 253 | 252 | 251 | 250 | 252 | 250 | 143 |
| TXN | 252 | 252 | 252 | 251 | 251 | 252 | 253 | 252 | 251 | 250 | 252 | 250 | 143 |
| AMD | 252 | 252 | 252 | 251 | 251 | 252 | 253 | 252 | 251 | 250 | 252 | 250 | 143 |
| INTC | 252 | 252 | 252 | 251 | 251 | 252 | 253 | 252 | 251 | 250 | 252 | 250 | 143 |
| QCOM | 252 | 252 | 252 | 251 | 251 | 252 | 253 | 252 | 251 | 250 | 252 | 250 | 143 |
| IBM | 252 | 252 | 252 | 251 | 251 | 252 | 253 | 252 | 251 | 250 | 252 | 250 | 143 |
| GOOGL | 252 | 252 | 252 | 251 | 251 | 252 | 253 | 252 | 251 | 250 | 252 | 250 | 143 |
| META | 252 | 252 | 252 | 251 | 251 | 252 | 253 | 252 | 251 | 250 | 252 | 250 | 143 |
| NFLX | 252 | 252 | 252 | 251 | 251 | 252 | 253 | 252 | 251 | 250 | 252 | 250 | 143 |
| DIS | 252 | 252 | 252 | 251 | 251 | 252 | 253 | 252 | 251 | 250 | 252 | 250 | 143 |

Skipped tickers (under 200 rows): none.
Implied vol rows: 20011, 2019-06-01 to 2026-06-30.
Earliest earnings date per ticker: AAPL 2002-04-17, ACN 2002-04-11, ADBE 2002-03-14, AMD 2002-01-16, AVGO 2009-12-03, CRM 2004-08-19, CSCO 2002-05-07, DIS 2002-01-31, GOOGL 2004-10-21, IBM 2002-01-17, INTC 2002-04-16, META 2012-07-26, MSFT 2002-01-17, NFLX 2002-07-24, NVDA 2002-05-22, QCOM 2002-01-24, TXN 2002-01-28.
Dropped train setups: exit_after_cutoff 0, exit_past_data 0, stale_iv 107, earnings_in_window 398.
Dropped validation setups: exit_after_cutoff 0, exit_past_data 0, stale_iv 0, earnings_in_window 34.

Earnings caveat: actual report dates are used; companies usually announce dates weeks ahead, so the look-ahead is small but not zero.

## 4. Results

| Run | n | blocks | win | mean | median | 95% interval | worst trade / 10-day window |
|---|---|---|---|---|---|---|---|
| v0 train | 398 | 133 | 22% | -34.62% | -46.88% | [-39.95%, -28.61%] | -99.94% / -631.15% |
| v0 validation | 34 | 12 | 26% | -18.38% | -48.73% | [-36.18%, +8.87%] | -95.74% / -486.63% |
| no-condition baseline, train | 2255 | 143 | 37% | -8.42% | -25.37% | [-14.16%, -1.70%] | -100.00% / -1111.80% |
| no-condition baseline, validation | 204 | 12 | 37% | -5.23% | -25.82% | [-16.36%, +5.99%] | -100.00% / -608.29% |
| random selection at the same rate, validation (reported only) | 32 | 10 | 25% | -25.60% | -39.08% | [-50.76%, -1.15%] | -97.82% / -215.90% |
| stricter cost (+10% buyer / -10% seller), validation | 34 | 12 | 26% | -25.80% | -53.40% | [-41.98%, -1.03%] | -96.12% / -524.21% |

Paired lower bound (v0 minus baseline, validation, 2.5th percentile): -31.73%.
Tail risk (train plus validation): worst trade -99.94%, worst 10-trading-day window -631.15%.

## 5. Coded checks and follow-ups

| Check | Passed | Note |
|---|---|---|
| evidence | yes | validation needs n >= 30 and at least 6 distinct 10-trading-day blocks |
| leakage | yes | no feature or trade date after 2026-06-30 (earnings features exempt, see caveat) |
| decay | no | validation mean -18.38% vs train mean -34.62% |
| shared_window | yes | 1 earlier audit(s) used this validation window. About 5% of plans with no real edge pass this test by chance; testing many variants of one idea raises that. |
| cost_realism | no | 100% of validation trades had earnings in the window (priced x1.20); stricter-cost lower bound -41.98% |
| tail_risk | yes | worst trade -99.94%, worst 10-day window -631.15% (train plus validation) |
| data_drops | yes | setups dropped for exits past the cutoff or the data, stale implied vol, missing earnings coverage |

Follow-ups: none run.
Note: follow-ups disabled for this run (--no-followups, the M1 behaviour).

## 6. Shared validation window

1 audit(s) have used this validation window before this one. About 5% of plans with no real edge pass this test by chance; testing many variants of one idea raises that.

## 7. Naysayer critique and Reporter prose

Naysayer: The base results are negative in both train and validation, and the validation sample is tiny (n=34, 12 blocks). The validation confidence interval barely crosses zero, but the median is still about -49%, so the central outcome is strongly negative and any positive upper bound is probably noise. The strategy underperforms the unconditional baseline in both periods, meaning the earnings-within-10d condition appears to worsen a losing straddle rather than add edge. Cost realism fails because all validation trades were earnings-event trades and the stricter lower bound is about -42%, so executable costs would make it worse. Tail risk is severe, with near-total single-trade losses and multi-hundred-percent 10-day windows. Reuse of the same validation window and many likely variants raises overfitting concerns.

Reporter: This audit tested whether buying at-the-money straddles on large tech stocks in the days before an earnings report made money over a 10-day holding period, using historical price and implied-volatility data. The results show that across the validation sample the average trade lost 18.38%, and even the most optimistic edge of the uncertainty range only just reached positive territory, while the typical trade lost far more than that. For a hobby trader, this means a straightforward pre-earnings straddle purchase on tech names did not hold up as an edge in this test, and it did worse than simply buying straddles without any earnings filter. The cost and tail-risk checks suggest that real-world frictions and rare but severe losses would make the picture worse, not better. This is not financial advice.

## 8. Recoveries

none

## 9. Cost and trace

LLM calls: 3 (prompt tokens 6025, completion tokens 3238), cost $0.0174 (upper bound). neatlogs trace: e8ced3b1fffa3b4d6e87f17f2d1aa10b.

## 10. Disclaimer

Not financial advice. Survivorship bias: the universe is today's large caps. One validation window (2026-01-01 to 2026-06-30) shared by every audit. Costs are approximated (no fees for stocks; straddle costs from an ATM formula with haircuts). No position sizing is given.
