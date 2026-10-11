# Hackathon_neatlogs

## Strategy Auditor (M1)

The main agent: a trading idea in plain English goes in, an evidence report with a verdict (`kill`, `inconclusive`, `promising`, `cannot_audit`) comes out. Paper trading and historical replay only; not financial advice. Spec: `docs/AUDITOR_SPEC.md`.

```bash
.venv/bin/python -m src.auditor "buy straddles on tech stocks before earnings"   # DeepSeek (needs DEEPSEEK_API_KEY in .env, balance >= $2)
.venv/bin/python -m src.auditor --id <audit_id> "<idea>"                          # fixed id (used by the server)
.venv/bin/python -m src.auditor --resume <audit_id>                               # continue an interrupted audit
.venv/bin/python -m src.auditor --fault dolthub_timeout "<idea>"                  # or --fault llm_empty: one injected failure, labelled INJECTED
.venv/bin/python -m src.auditor --provider fake "<idea>"                          # keyword fake LLM, development only (report says FAKE LLM)
```

Outputs per audit under `runs/audits/<audit_id>/`: `events.jsonl` (the event stream the UI replays), `state.json` (frozen plan v0 and its SHA-256, step results, LLM calls used), `report.md`. Every finished audit appends a line to `runs/audits/registry.jsonl`. Data caches: `data/cache/` (prices from Yahoo, implied vol from DoltHub, earnings dates). Demo audits are copied by hand to `results/audits/<audit_id>/` so they can be committed and replayed.

Tests: `.venv/bin/python -m pytest tests/test_auditor_*.py -q --basetemp=.pytest_tmp`.

## Mission control (M3)

Web interface that replays a recorded audit (`docs/AUDITOR_SPEC.md` section 16).

```bash
pip install -r requirements.txt            # or: .venv/bin/python -m pip install fastapi "uvicorn[standard]" httpx
cd ui && npm install && npm run build && cd ..
.venv/bin/python scripts/synthetic_audit.py --out runs/audits   # synthetic dev fixture, never for the demo
.venv/bin/python -m uvicorn src.auditor.server:app --port 8000  # open http://127.0.0.1:8000/
```

Development: `cd ui && npm run dev` (proxies `/api` to the server on :8000). Tests: `pytest tests/test_auditor_*.py` and `cd ui && npm test && npm run typecheck`.

