"""Mission-control server (AUDITOR_SPEC.md section 16).

Routes:
  GET  /api/audits                        list recorded audits (runs/audits, results/audits)
  GET  /api/audits/{id}/events            Server-Sent Events; ?replay=1&speed=1..8&from=SEQ replays
                                          the file paced by its timestamps; without replay=1 it
                                          tails a live run
  GET  /api/audits/{id}/report            the markdown report
  POST /api/audits {"idea"}               start a live audit (one at a time; 409 while running)
  /                                       the built frontend from ui/dist, when present

Run: .venv/bin/python -m uvicorn src.auditor.server:app --port 8000
"""
import asyncio
import json
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from .replay import clamp_speed, find_audit_dir, read_event_lines, replay_delays

REPO = Path(__file__).resolve().parents[2]
DEFAULT_ROOTS = [REPO / "runs" / "audits", REPO / "results" / "audits"]
DEFAULT_UI_DIST = REPO / "ui" / "dist"
SSE_HEADERS = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
TERMINAL = {"verdict", "error"}


def _sse(seq, line):
    return "id: %s\ndata: %s\n\n" % (seq, line)


def _summary(audit_dir):
    events = [e for _, e in read_event_lines(audit_dir / "events.jsonl")]
    started = next((e for e in events if e.get("type") == "audit_started"), None)
    return {"audit_id": audit_dir.name,
            "idea": (started or {}).get("payload", {}).get("idea", ""),
            "started_at": (started or {}).get("ts", ""),
            "finished": any(e.get("type") in TERMINAL for e in events)}


def create_app(roots=None, ui_dist=None, runner=None, sleep=asyncio.sleep):
    """Build the app. `roots` are searched in order for <audit_id>/events.jsonl; `sleep` paces replays."""
    roots = [Path(r) for r in (roots if roots is not None else DEFAULT_ROOTS)]
    ui_dist = Path(ui_dist) if ui_dist is not None else DEFAULT_UI_DIST
    app = FastAPI(title="Strategy Auditor mission control")

    def audit_dir_or_404(audit_id):
        found = find_audit_dir(audit_id, roots)
        if found is None:
            raise HTTPException(404, "unknown audit %r" % audit_id)
        return found

    @app.get("/api/audits")
    def list_audits():
        seen, out = set(), []
        for root in roots:
            if not root.is_dir():
                continue
            for d in sorted(root.iterdir()):
                if d.name in seen or not (d / "events.jsonl").is_file():
                    continue
                seen.add(d.name)
                try:
                    out.append(_summary(d))
                except (ValueError, OSError):
                    continue
        return sorted(out, key=lambda a: a["started_at"], reverse=True)

    @app.get("/api/audits/{audit_id}/events")
    async def events(audit_id: str, request: Request, replay: str | None = None,
                     speed: str | None = None, from_seq: str | None = Query(None, alias="from")):
        audit_dir = audit_dir_or_404(audit_id)
        raw_from = from_seq if from_seq is not None else request.headers.get("last-event-id")
        try:
            after = int(raw_from) if raw_from is not None else 0
        except ValueError:
            after = 0
        if replay in ("1", "true", "yes"):
            gen = _replay(audit_dir / "events.jsonl", clamp_speed(speed), after)
        else:
            raise HTTPException(501, "live mode is not built yet")
        return StreamingResponse(gen, media_type="text/event-stream", headers=SSE_HEADERS)

    async def _replay(path, speed, after):
        pairs = read_event_lines(path)
        delays = replay_delays([e for _, e in pairs], speed)
        for (line, event), delay in zip(pairs, delays):
            if int(event.get("seq", 0)) <= after:
                continue
            if delay:
                await sleep(delay)
            yield _sse(event.get("seq"), line)
        yield "event: end\ndata: {}\n\n"

    @app.get("/api/audits/{audit_id}/report")
    def report(audit_id: str):
        path = audit_dir_or_404(audit_id) / "report.md"
        if not path.is_file():
            raise HTTPException(404, "no report for audit %r" % audit_id)
        return PlainTextResponse(path.read_text(encoding="utf-8"), media_type="text/markdown")

    if (ui_dist / "index.html").is_file():
        app.mount("/", StaticFiles(directory=str(ui_dist), html=True), name="ui")
    return app


app = create_app()
