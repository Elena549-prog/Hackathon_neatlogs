# Spike scripts (reference code)

Throwaway research scripts from 2026-10-10, rescued from a session scratchpad on 2026-10-11. They are reference code for the Strategy Auditor (`docs/AUDITOR_SPEC.md`, section 11). The auditor does not run them. Results below are from `docs/STATUS.md`.

| Script | What it measured | Headline result |
|---|---|---|
| `signal_test.py` | Do market, earnings or volume features add validation signal over the 7 price features (5 stocks)? | No edge. |
| `signal_test_50.py` | Validation signal for the +5%/-3% bet on 50 stocks, train 2015–2025 | AUC 0.45–0.48; patterns flipped in 2026. |
| `signal_test_50_cfg.py` | Shared config: the 50 tickers and the train/validation windows | Config only, no result. |
| `vol_test_50.py` | Is the size of the next 10-day move (±5%) predictable on 50 stocks? | Yes, AUC 0.67. |
| `straddle_test.py` | Do 10-day at-the-money straddles have a predictable edge on 50 stocks (implied vol from DoltHub)? | No. Buying loses 4–7% per trade; models can't pick winners (AUC 0.49–0.52). |
| `build_business_model.py` | Builds `results/business_model.xlsx` for cfo.ai | Prices a $19/month watchlist for the trading swarm (to be reworked per audit). |
| `verify_model.py` | Evaluates every workbook formula with pycel and checks key outputs against a Python model | Formulas verified. |

Paths and caches:
- Run from the repo root (the scripts import `src.*`). Some take an output path or a directory as `sys.argv[1]`.
- `straddle_test.py` reads and writes its caches (`iv_50.csv`, `straddles_50.csv`) next to itself. `vol_test_50.py` imports `signal_test_50_cfg` from the directory given as `sys.argv[1]`.
- The CSV caches are in `data/cache/` (gitignored): `iv_50.csv`, `setups_50.csv`, `setups_plus.csv`, `straddles_50.csv`. Copy them next to a script, or pass their path, before re-running.
