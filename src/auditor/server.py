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
import datetime as dt
import json
import secrets
import subprocess
import sys
import threading
import time
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .replay import clamp_speed, event_seq, find_audit_dir, read_event_lines, replay_delays

REPO = Path(__file__).resolve().parents[2]
DEFAULT_ROOTS = [REPO / "runs" / "audits", REPO / "results" / "audits"]
DEFAULT_UI_DIST = REPO / "ui" / "dist"
SSE_HEADERS = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
TERMINAL = {"verdict", "error"}


LIVE_POLL_S = 0.2
LIVE_GRACE_S = 5.0


class IdeaBody(BaseModel):
    idea: str


class AuditRunner:
    """Runs one auditor subprocess at a time and appends an `error` event if it exits without a verdict."""

    def __init__(self, root, command=None):
        self.root = Path(root)
        self.command = command or (lambda aid, idea: [sys.executable, "-m", "src.auditor", "--id", aid, idea])
        self._proc, self._audit_id, self._exited_at = None, None, None
        self._lock = threading.Lock()

    @property
    def running(self):
        return self._proc is not None and self._proc.poll() is None

    def owns(self, audit_id):
        return audit_id == self._audit_id

    def exited_at(self, audit_id):
        return self._exited_at if self.owns(audit_id) and not self.running else None

    def start(self, idea):
        with self._lock:
            if self.running:
                raise RuntimeError("an audit is already running")
            audit_id = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d-%H%M%S") + "-" + secrets.token_hex(2)
            self.root.mkdir(parents=True, exist_ok=True)
            self._proc = subprocess.Popen(self.command(audit_id, idea), cwd=str(REPO))
            self._audit_id, self._exited_at = audit_id, None
            threading.Thread(target=self._watch, args=(self._proc, audit_id), daemon=True).start()
            return audit_id

    def _watch(self, proc, audit_id):
        code = proc.wait()
        path = self.root / audit_id / "events.jsonl"
        events = [e for _, e in read_event_lines(path)] if path.is_file() else []
        if not any(e.get("type") in TERMINAL for e in events):
            seq = max((event_seq(e) or 0 for e in events), default=0) + 1
            event = {"seq": seq, "ts": dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z"),
                     "audit_id": audit_id, "type": "error", "agent": None,
                     "payload": {"step": "run", "message": "auditor exited with code %s without a verdict" % code}}
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(event) + "\n")
        self._exited_at = time.time()


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
    runner = runner or AuditRunner(roots[0])
    app = FastAPI(title="Strategy Auditor mission control")

    def audit_dir_or_404(audit_id):
        found = find_audit_dir(audit_id, roots)
        if found is None:
            raise HTTPException(404, "unknown audit %r" % audit_id)
        return found

    async def audit_dir_or_wait(audit_id):
        """A just-started live audit may not have written its file yet: wait briefly for it."""
        deadline = time.time() + 3.0
        while runner.owns(audit_id) and find_audit_dir(audit_id, roots) is None and time.time() < deadline:
            await asyncio.sleep(LIVE_POLL_S)
        return audit_dir_or_404(audit_id)

    @app.post("/api/audits")
    def start_audit(body: IdeaBody):
        try:
            return {"audit_id": runner.start(body.idea)}
        except RuntimeError as e:
            raise HTTPException(409, str(e))

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
        audit_dir = await audit_dir_or_wait(audit_id)
        raw_from = from_seq if from_seq is not None else request.headers.get("last-event-id")
        try:
            after = int(raw_from) if raw_from is not None else 0
        except ValueError:
            after = 0
        if replay in ("1", "true", "yes"):
            gen = _replay(audit_dir / "events.jsonl", clamp_speed(speed), after)
        else:
            gen = _live(audit_dir / "events.jsonl", audit_id, after)
        return StreamingResponse(gen, media_type="text/event-stream", headers=SSE_HEADERS)

    async def _replay(path, speed, after):
        pairs = read_event_lines(path)
        delays = replay_delays([e for _, e in pairs], speed)
        for (line, event), delay in zip(pairs, delays):
            seq = event_seq(event)
            if seq is not None and seq <= after:
                continue
            if delay:
                await sleep(delay)
            yield _sse(event.get("seq"), line)
        yield "event: end\ndata: {}\n\n"

    async def _live(path, audit_id, after):
        """Tail the file: complete lines only; end after error, after verdict + report_ready, or 5 s after exit."""
        seen_verdict = False
        while True:
            for line, event in read_event_lines(path) if path.is_file() else []:
                seq = event_seq(event)
                if seq is not None and seq <= after:
                    continue
                after = seq if seq is not None else after
                yield _sse(seq, line)
                kind = event.get("type")
                seen_verdict = seen_verdict or kind == "verdict"
                if kind == "error" or (kind == "report_ready" and seen_verdict):
                    yield "event: end\ndata: {}\n\n"
                    return
            exited = runner.exited_at(audit_id)
            if exited is not None and time.time() - exited > LIVE_GRACE_S:
                yield "event: end\ndata: {}\n\n"
                return
            await asyncio.sleep(LIVE_POLL_S)

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
