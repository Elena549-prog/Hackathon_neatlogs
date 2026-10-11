# Hackathon_neatlogs

## Mission control (M3)

Web interface that replays a recorded audit (`docs/AUDITOR_SPEC.md` section 16).

```bash
pip install -r requirements.txt            # or: .venv/bin/python -m pip install fastapi "uvicorn[standard]" httpx
cd ui && npm install && npm run build && cd ..
.venv/bin/python scripts/synthetic_audit.py --out runs/audits   # synthetic dev fixture, never for the demo
.venv/bin/python -m uvicorn src.auditor.server:app --port 8000  # open http://127.0.0.1:8000/
```

Development: `cd ui && npm run dev` (proxies `/api` to the server on :8000). Tests: `pytest tests/test_auditor_*.py` and `cd ui && npm test && npm run typecheck`.

