# Strategy Auditor report: KILLED

straddle_sell on mega_cap (10 tickers): enter when vol_20d < 0.02; hold 10 days. Not tested: Option bid-ask spreads, liquidity, and exact strike selection.; Margin requirements and capital allocation.; Early assignment risk and dividend effects..

## 1. What was tested and the verdict

**Verdict: KILLED.** validation mean <= 0 with enough evidence

Headline: validation n = 70, mean per trade -10.18%, lower bound -23.94%, paired lower bound vs baseline -21.37%.

## 2. Idea, plan v0, assumptions

Idea: sell straddles on low-volatility mega-caps

Plan v0 (frozen before any backtest), SHA-256 `b8d1dc5558d2a84a50902e138f649716d91cf89650532835f5e45cf52e4957db`:

```json
{
  "assumptions": [
    "'sell straddles' read as short at-the-money straddle held for 10 days (family straddle_sell).",
    "'low-volatility' read as 20-day daily return standard deviation below 0.02 (2%).",
    "'mega-caps' mapped to the mega_cap universe group."
  ],
  "conditions": {
    "vol_20d": [
      "<",
      0.02
    ]
  },
  "core_trigger_tested": true,
  "family": "straddle_sell",
  "hypothesis": "Selling 10-day at-the-money straddles on mega-cap stocks when 20-day realized volatility is below 2% will be profitable.",
  "not_tested": [
    "Option bid-ask spreads, liquidity, and exact strike selection.",
    "Margin requirements and capital allocation.",
    "Early assignment risk and dividend effects."
  ],
  "refused": false,
  "universe_group": "mega_cap"
}
```

Assumptions: 'sell straddles' read as short at-the-money straddle held for 10 days (family straddle_sell).; 'low-volatility' read as 20-day daily return standard deviation below 0.02 (2%).; 'mega-caps' mapped to the mega_cap universe group..
Not tested: Option bid-ask spreads, liquidity, and exact strike selection.; Margin requirements and capital allocation.; Early assignment risk and dividend effects..
Universe: mega_cap = AAPL, MSFT, NVDA, GOOGL, AMZN, META, AVGO, TSLA, BRK-B, LLY.

## 3. Data coverage

| Ticker | 2014 | 2015 | 2016 | 2017 | 2018 | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| AAPL | 252 | 252 | 252 | 251 | 251 | 252 | 253 | 252 | 251 | 250 | 252 | 250 | 143 |
| MSFT | 252 | 252 | 252 | 251 | 251 | 252 | 253 | 252 | 251 | 250 | 252 | 250 | 143 |
| NVDA | 252 | 252 | 252 | 251 | 251 | 252 | 253 | 252 | 251 | 250 | 252 | 250 | 143 |
| GOOGL | 252 | 252 | 252 | 251 | 251 | 252 | 253 | 252 | 251 | 250 | 252 | 250 | 143 |
| AMZN | 252 | 252 | 252 | 251 | 251 | 252 | 253 | 252 | 251 | 250 | 252 | 250 | 143 |
| META | 252 | 252 | 252 | 251 | 251 | 252 | 253 | 252 | 251 | 250 | 252 | 250 | 143 |
| AVGO | 252 | 252 | 252 | 251 | 251 | 252 | 253 | 252 | 251 | 250 | 252 | 250 | 143 |
| TSLA | 252 | 252 | 252 | 251 | 251 | 252 | 253 | 252 | 251 | 250 | 252 | 250 | 143 |
| BRK-B | 252 | 252 | 252 | 251 | 251 | 252 | 253 | 252 | 251 | 250 | 252 | 250 | 143 |
| LLY | 252 | 252 | 252 | 251 | 251 | 252 | 253 | 252 | 251 | 250 | 252 | 250 | 143 |

Skipped tickers (under 200 rows): none.
Implied vol rows: 11321, 2019-06-01 to 2026-06-30.
Earliest earnings date per ticker: AAPL 2002-04-17, AMZN 2002-04-23, AVGO 2009-12-03, BRK-B 2010-05-07, GOOGL 2004-10-21, LLY 2002-01-24, META 2012-07-26, MSFT 2002-01-17, NVDA 2002-05-22, TSLA 2010-11-09.
Dropped train setups: exit_after_cutoff 34, exit_past_data 0, stale_iv 400, earnings_in_window 140.
Dropped validation setups: exit_after_cutoff 0, exit_past_data 0, stale_iv 0, earnings_in_window 11.

## 4. Results

| Run | n | blocks | win | mean | median | 95% interval | worst trade / 10-day window |
|---|---|---|---|---|---|---|---|
| v0 train | 780 | 144 | 58% | -4.44% | +16.26% | [-11.83%, +2.56%] | -437.80% / -1276.54% |
| v0 validation | 70 | 12 | 53% | -10.18% | +2.57% | [-23.94%, +4.18%] | -208.37% / -440.97% |
| no-condition baseline, train | 1267 | 143 | 58% | -5.22% | +15.60% | [-12.76%, +1.80%] | -634.49% / -1729.75% |
| no-condition baseline, validation | 120 | 12 | 59% | +2.02% | +18.41% | [-12.69%, +18.35%] | -204.22% / -482.46% |
| random selection at the same rate, validation (reported only) | 76 | 12 | 62% | +8.23% | +24.51% | [-5.91%, +23.84%] | -204.22% / -210.23% |
| stricter cost (+10% buyer / -10% seller), validation | 70 | 12 | 46% | -22.42% | -8.25% | [-37.71%, -6.47%] | -242.63% / -556.64% |

Paired lower bound (v0 minus baseline, validation, 2.5th percentile): -21.37%.
Tail risk (train plus validation): worst trade -437.80%, worst 10-trading-day window -1276.54%. Seller losses: worst trade -5.9 average premiums (-25.26% of stock price); worst window -1276.54% vs total validation gain -712.45%.

## 5. Coded checks and follow-ups

| Check | Passed | Note |
|---|---|---|
| evidence | yes | validation needs n >= 30 and at least 6 distinct 10-trading-day blocks |
| leakage | yes | no feature or trade date after 2026-06-30 (earnings features exempt, see caveat) |
| decay | no | validation mean -10.18% vs train mean -4.44% |
| shared_window | yes | 5 earlier audit(s) used this validation window. About 5% of plans with no real edge pass this test by chance; testing many variants of one idea raises that. |
| cost_realism | no | 16% of validation trades had earnings in the window (priced x1.20); stricter-cost lower bound -37.71% |
| tail_risk | no | worst trade -437.80%, worst 10-day window -1276.54% (train plus validation) |
| data_drops | yes | setups dropped for exits past the cutoff or the data, stale implied vol, missing earnings coverage |

Follow-ups: none run.

## 6. Shared validation window

5 audit(s) have used this validation window before this one. About 5% of plans with no real edge pass this test by chance; testing many variants of one idea raises that.

## 7. Naysayer critique and Reporter prose

Naysayer's doubts before the follow-ups: The base validation mean is -10.18%, already negative and worse than the train mean of -4.44%, so there is no positive result to defend.; The stricter-cost lower bound is -37.71% in validation, and 16% of validation trades had earnings in the window, so costs and earnings timing may be driving the negative performance.; Tail risk check failed with a worst trade of -437.80% and worst 10-day window of -1276.54%, meaning the loss tail dominates any positive median or win rate..

Naysayer: The validation result is worse than training, with mean -10.18% versus -4.44%, and the stricter-cost confidence interval is entirely negative, so whatever edge existed does not survive out-of-sample. The no-condition baseline has a validation mean of +2.02% while the conditioned strategy is negative, suggesting the vol<2% filter adds no value or is detrimental. Tail risk is severe: the worst trade is -437.80% and the worst 10-day window is -1,276.54%, which implies losses far beyond collected premium and casts doubt on realistic viability. The cost realism check fails because earnings events are only partially priced and option bid-ask spreads, liquidity, margin, and early assignment are not modeled. The validation window has been reused in five earlier audits, increasing false-discovery risk, and the sample is small with only 70 validation trades after filters.

Reporter: This report tested a strategy that sells at-the-money straddles on large-cap stocks when recent volatility is low, holding each position for ten days. The validation sample of 70 trades had a negative average return of -10.18%, which was worse than the training sample and worse than a baseline that skipped the volatility filter. The worst single trade and worst ten-day window show losses far larger than the premium collected, so the loss tail dominates the positive win rate and median. The auditor's verdict is KILLED, meaning the evidence did not support the idea under the tested conditions. Several real-world costs and risks were not modeled, and the validation window has been reused before, so this is not a complete picture of live trading.

## 8. Recoveries

none

## 9. Cost and trace

LLM calls: 4 (prompt tokens 7764, completion tokens 7439), cost $0.0365 (upper bound). neatlogs trace: 436ae42eabee193059af98ce63b6e3db.

## 10. Disclaimer

Not financial advice. Survivorship bias: the universe is today's large caps. One validation window (2026-01-01 to 2026-06-30) shared by every audit. Costs are approximated (no fees for stocks; straddle costs from an ATM formula with haircuts). No position sizing is given.
