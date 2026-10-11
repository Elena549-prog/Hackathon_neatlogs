# Strategy Auditor report: KILLED

straddle_buy on tech (17 tickers): enter when earnings_within_10d >= 1; hold 10 days. Not tested: Exact option strike and expiration selection beyond at-the-money.; Richness of implied volatility at entry.; Actual earnings date and time precision.; Intraday entry or exit timing..

## 1. What was tested and the verdict

**Verdict: KILLED.** validation mean <= 0 with enough evidence

Headline: validation n = 34, mean per trade -18.38%, lower bound -36.18%, paired lower bound vs baseline -31.73%.

## 2. Idea, plan v0, assumptions

Idea: buy straddles on tech before earnings

Plan v0 (frozen before any backtest), SHA-256 `11e4261d7fca8ab723dfc9241f95e3e769cb6bc23a4c9933dcd9f072a66ef1d8`:

```json
{
  "assumptions": [
    "'buy straddles on tech before earnings' read as entering an at-the-money straddle at the close when the stock has an earnings report in the next 10 trading days.",
    "'tech' read as the predefined tech universe.",
    "Straddle positions are held for 10 trading days as specified by the straddle_buy family."
  ],
  "conditions": {
    "earnings_within_10d": [
      ">=",
      1
    ]
  },
  "core_trigger_tested": true,
  "family": "straddle_buy",
  "hypothesis": "Buying at-the-money straddles on tech stocks when earnings are within the next 10 trading days will capture volatility expansion.",
  "not_tested": [
    "Exact option strike and expiration selection beyond at-the-money.",
    "Richness of implied volatility at entry.",
    "Actual earnings date and time precision.",
    "Intraday entry or exit timing."
  ],
  "refused": false,
  "universe_group": "tech"
}
```

Assumptions: 'buy straddles on tech before earnings' read as entering an at-the-money straddle at the close when the stock has an earnings report in the next 10 trading days.; 'tech' read as the predefined tech universe.; Straddle positions are held for 10 trading days as specified by the straddle_buy family..
Not tested: Exact option strike and expiration selection beyond at-the-money.; Richness of implied volatility at entry.; Actual earnings date and time precision.; Intraday entry or exit timing..
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
| shared_window | yes | 6 earlier audit(s) used this validation window. About 5% of plans with no real edge pass this test by chance; testing many variants of one idea raises that. |
| cost_realism | no | 100% of validation trades had earnings in the window (priced x1.20); stricter-cost lower bound -41.98% |
| tail_risk | yes | worst trade -99.94%, worst 10-day window -631.15% (train plus validation) |
| data_drops | yes | setups dropped for exits past the cutoff or the data, stale implied vol, missing earnings coverage |

Follow-ups: none run.

## 6. Shared validation window

6 audit(s) have used this validation window before this one. About 5% of plans with no real edge pass this test by chance; testing many variants of one idea raises that.

## 7. Naysayer critique and Reporter prose

Naysayer's doubts before the follow-ups: The validation mean is already negative at -18.38%, and the stricter-cost validation confidence interval is entirely below zero (-41.98% to -1.03%), so there is no positive result to validate.; The strategy underperforms the baseline validation mean of -5.23% by roughly 13 percentage points, with a validation win rate of 26.5% versus the baseline's 37.3%.; The sample is small and noisy: only 34 validation trades in 12 blocks, and the validation CI spans -36.18% to 8.87%, so any claimed edge is not statistically distinguishable from a large loss.; Cost realism fails: 100% of validation trades contained earnings and were priced at 1.20; the validation mean worsens to -25.80% under stricter costs.; Tail risk is extreme, with a worst trade of -99.94% and a worst 10-day window of -631.15%, making any apparent stabilization fragile..

Naysayer: This backtest shows a strategy that loses money in both training and validation, with mean returns of -34.6% and -18.4% respectively, and the loss is worse than the no-condition baseline (-8.4%/-5.2%). The validation sample is very small (34 trades, 12 blocks), and its confidence interval still includes zero, so there is no reliable evidence of an edge. The apparent improvement from train to validation is likely noise rather than robustness, and the condition merely selects a subset of even worse trades. Stricter cost assumptions push the validation lower bound to -42%, reinforcing that the realistic outcome is strongly negative. The single worst trade lost nearly 100%, and the worst 10-day window lost 631%, indicating extreme tail risk.

Reporter: This report tested a specific options strategy on 17 large technology stocks: buying an at-the-money straddle when earnings are due within 10 trading days and holding it for 10 days. Across 398 training trades the average result was -34.62%, and across 34 validation trades it was -18.38%, both worse than the no-condition baseline's -8.42% and -5.23%. The validation sample is small and its interval still includes a small positive value, so the numbers are consistent with a losing strategy rather than a demonstrated edge. The very large worst-case losses shown here illustrate how quickly a long straddle can lose value if the expected price move does not materialize.

## 8. Recoveries

- [INJECTED] DoltHub timeout on window 2026-06-17..2026-06-30: injected DoltHub timeout: retried after 2 s

## 9. Cost and trace

LLM calls: 4 (prompt tokens 8106, completion tokens 5136), cost $0.0274 (upper bound). neatlogs trace: ddc14bc17377d6db8c9afa65359695b0.

## 10. Disclaimer

Not financial advice. Survivorship bias: the universe is today's large caps. One validation window (2026-01-01 to 2026-06-30) shared by every audit. Costs are approximated (no fees for stocks; straddle costs from an ATM formula with haircuts). No position sizing is given.
