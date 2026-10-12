# Strategy Auditor report: KILLED

straddle_buy on tech (17 tickers): enter when earnings_within_10d >= 1; hold 10 days. Not tested: Exact number of days until earnings beyond a binary window.; Directional view or post-earnings drift.; Option-specific details such as strike selection nuances, IV term structure, or transaction costs..

## 1. What was tested and the verdict

**Verdict: KILLED.** validation mean <= 0 with enough evidence

Headline: validation n = 34, mean per trade -18.38%, lower bound -36.18%, paired lower bound vs baseline -31.73%.

## 2. Idea, plan v0, assumptions

Idea: buy straddles on tech before earnings

Plan v0 (frozen before any backtest), SHA-256 `7b4fff7c83a110ea4e306756911c58ad8481687a0a3163171395ca15949b830a`:

```json
{
  "assumptions": [
    "'tech' maps to the predefined tech universe group.",
    "'before earnings' is read as an earnings report occurring within the next 10 trading days.",
    "Straddles are held for 10 days per the straddle family definition; exit is ignored."
  ],
  "conditions": {
    "earnings_within_10d": [
      ">=",
      1
    ]
  },
  "core_trigger_tested": true,
  "family": "straddle_buy",
  "hypothesis": "Buying at-the-money straddles on tech stocks within 10 trading days before an earnings report will profit from an earnings-related volatility expansion.",
  "not_tested": [
    "Exact number of days until earnings beyond a binary window.",
    "Directional view or post-earnings drift.",
    "Option-specific details such as strike selection nuances, IV term structure, or transaction costs."
  ],
  "refused": false,
  "universe_group": "tech"
}
```

Assumptions: 'tech' maps to the predefined tech universe group.; 'before earnings' is read as an earnings report occurring within the next 10 trading days.; Straddles are held for 10 days per the straddle family definition; exit is ignored..
Not tested: Exact number of days until earnings beyond a binary window.; Directional view or post-earnings drift.; Option-specific details such as strike selection nuances, IV term structure, or transaction costs..
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
| shared_window | yes | 4 earlier audit(s) used this validation window. About 5% of plans with no real edge pass this test by chance; testing many variants of one idea raises that. |
| cost_realism | no | 100% of validation trades had earnings in the window (priced x1.20); stricter-cost lower bound -41.98% |
| tail_risk | yes | worst trade -99.94%, worst 10-day window -631.15% (train plus validation) |
| data_drops | yes | setups dropped for exits past the cutoff or the data, stale implied vol, missing earnings coverage |

Follow-ups: none run.

## 6. Shared validation window

4 audit(s) have used this validation window before this one. About 5% of plans with no real edge pass this test by chance; testing many variants of one idea raises that.

## 7. Naysayer critique and Reporter prose

Naysayer's doubts before the follow-ups: Validation mean is -18.38%, so there is no positive result to test; the strategy lost money net of the audit assumptions.; Validation sample is small (n=34, 12 blocks), and the 95% CI spans zero, so the negative point estimate is not even robustly different from zero.; The decay check failed: validation mean -18.38% vs train -34.62% indicates instability/overfitting rather than a real stable edge.; Cost realism failed with 100% of validation trades in earnings windows and stricter-cost lower bound -41.98%, so return estimates are fragile..

Naysayer: This condition looks worse than doing nothing, not a tradable edge. The validation sample is only 34 trades over 12 blocks and the confidence interval spans zero, so it is too small to separate noise from effect. The strategy's validation mean of -18.4% is far below the no-condition baseline mean of -5.2%, meaning the earnings window condition appears to select worse straddle outcomes rather than an exploitable pattern. The validation result also shows large decay from training (-34.6% to -18.4%), and with 100% of trades in earnings windows the cost adjustment is severe; the stricter lower bound drops to about -42%. Worst-case outcomes are extreme: a single trade near -100% and a 10-day window near -631%, and 107 dropped stale-IV observations in training may bias the remaining sample. Because this validation window was reused across four earlier audits and the tested feature is a simple binary cutoff, the result is likely a fragile, multiple-testing artifact.

Reporter: This report tested a simple idea: buy at-the-money straddles on large tech stocks when earnings were due within 10 trading days, holding for 10 days. The validation sample was small (34 trades across 12 blocks), and the mean outcome was -18.38%, meaning the average trade lost money net of the audit's cost assumptions. That result was worse than a no-condition baseline that averaged -5.23%, so the earnings-window filter did not appear to help. Because the confidence interval spans zero and the validation window has been reused in earlier audits, the numbers are best read as weak evidence rather than a clear edge either way. This is not financial advice.

## 8. Recoveries

none

## 9. Cost and trace

LLM calls: 4 (prompt tokens 8012, completion tokens 3843), cost $0.0222 (upper bound). neatlogs trace: d15017b0b19406f2ed867871071fab13.

## 10. Disclaimer

Not financial advice. Survivorship bias: the universe is today's large caps. One validation window (2026-01-01 to 2026-06-30) shared by every audit. Costs are approximated (no fees for stocks; straddle costs from an ATM formula with haircuts). No position sizing is given.
