# Strategy Auditor: before (M1, no follow-ups) vs after (M2, follow-ups F1-F4)

Metrics fixed in AUDITOR_SPEC section 17 before any run: verdict per idea, downgrades with reasons, LLM calls, cost and wall time per audit. Expected verdicts were written in section 13 first. Cost is the wrapper's upper bound; check it against the neatlogs traces.

| Idea | Expected | Run | Verdict | Downgrades | Follow-ups (rule) | LLM calls | Cost | Wall time |
|---|---|---|---|---|---|---|---|---|
| buy dips in an uptrend | kill | before | inconclusive | none | none | 3 | $0.0232 | 45 s |
| buy dips in an uptrend | kill | after | not run yet | | | | | |
| buy straddles on tech before earnings | kill | before | kill | none | none | 3 | $0.0174 | 31 s |
| buy straddles on tech before earnings | kill | after | not run yet | | | | | |
| sell straddles on low-volatility mega-caps | inconclusive or promising (tail risk decides) | before | kill | none | none | 3 | $0.0161 | 25 s |
| sell straddles on low-volatility mega-caps | inconclusive or promising (tail risk decides) | after | not run yet | | | | | |
