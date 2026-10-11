# M3 Mission-Control Interface (Replay Mode) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A web interface that replays a recorded audit `events.jsonl` as a mission-control screen: command bar, agent graph, equity curves, verdict stamp, footer meters, with play/pause and 1–8× speed.

**Architecture:** A FastAPI server (`src/auditor/server.py`) streams an audit's events over Server-Sent Events, paced from the file's timestamps (gaps capped at 2 s, divided by speed), serves the markdown report, and serves the built frontend from `ui/dist`. The React app keeps one pure reducer (`ui/src/state.ts`) that folds events into screen state; every component renders only that state. Live mode (subprocess per audit) is a thin layer on the same server and is stretch; the core of this plan is replay.

**Tech Stack:** Python 3.13 venv (`.venv/bin/python`), FastAPI, uvicorn, httpx (tests), pytest. Node 24, Vite 7, React 19, TypeScript 5.9, Tailwind 4 (`@tailwindcss/vite`), Framer Motion 12, TradingView `lightweight-charts` 5, Vitest.

**Spec:** `docs/AUDITOR_SPEC.md` section 16 (event contract, layout, motion, replay and honesty rules, tests, cut rule). Sections 4–9 define the agents, verdicts and demo ideas the UI shows. Section 13 lists the three demo ideas.

## Global Constraints

- Branch `m3-ui`, never `main`. Commit after each task. No secrets committed; `.env` stays out.
- The UI shows only numbers from events. It computes nothing itself except running totals of `llm_call` events for the footer meters.
- No placeholder or invented values in any build that is recorded or shown. The development fixture is synthetic: its idea text starts with `SYNTHETIC FIXTURE` and it lives under `runs/audits/` (gitignored), never under `results/audits/`.
- Event line: `{"seq", "ts", "audit_id", "type", "agent", "payload"}`; `agent` is one of `planner|researcher|mathematician|naysayer|reporter|triage` or `null`.
- Event types and required payload fields: the section 16 table, copied into `src/auditor/events.py` `EVENT_TYPES`.
- Replay: speed 1–8, gaps between events capped at 2 s before dividing by speed, label REPLAY with the original run date (`audit_started.ts`).
- Verdict stamp copy and colours: `KILLED` red, `INCONCLUSIVE` amber, `PROMISING` green, `CANNOT AUDIT` grey. PROMISING subtitle: "Passed a 6-month historical screen. Not a forecast. Not financial advice." INCONCLUSIVE subtitle: "inconclusive: a strategy with no real edge lands here about half the time".
- Demo idea chips, exact text: "buy dips in an uptrend", "buy straddles on tech before earnings", "sell straddles on low-volatility mega-caps".
- Motion: 150–600 ms except the verdict reveal; every animation marks an event; honour `prefers-reduced-motion`; no decorative loops.
- Layout designed for 1920×1080, usable from 1280 px wide. Fonts from Google Fonts: a sans for UI, a monospace for numbers and logs.
- Server: unknown audit id → 404; second live audit while one runs → 409; a child that exits without `verdict` or `error` gets an appended `error` event with the next `seq`.

## Review Focus

1. A partially written last line in `events.jsonl` (live tail or interrupted run) must be skipped, not parsed as JSON and crash the stream. Test in Task 2.
2. Equity payloads with fewer than 2 points (or an empty validation set for `cannot_audit`) must render an empty chart, not throw inside lightweight-charts. Test in Task 8.
3. A `verdict` event arriving before any `backtest_result` (cannot_audit path) must still show the stamp with the reason and no headline numbers. Test in Task 5 (reducer).
4. Pausing then resuming must not replay events already shown: resume opens the stream from the next seq. Test in Task 3 (`from` parameter) and Task 6.
5. `speed` outside 1–8 or non-numeric must clamp, not 500. Test in Task 3.

---

### Task 1: Branch, requirements, event schema and the synthetic fixture generator

**Files:**
- Create: `requirements.txt`
- Create: `src/auditor/__init__.py` (empty)
- Create: `src/auditor/events.py`
- Create: `scripts/synthetic_audit.py`
- Test: `tests/test_auditor_events.py`

**Interfaces:**
- Produces: `AGENTS: frozenset[str]`; `EVENT_TYPES: dict[str, tuple[str, ...]]` (type → required payload field names, exactly the section 16 table); `validate_event(obj: object) -> list[str]` returning an empty list for a valid event, else human-readable problems (missing top-level key, bad `agent`, unknown `type`, missing payload field, non-int `seq`); `scripts/synthetic_audit.py` `write_synthetic_audit(dir: Path, audit_id: str = "synthetic-demo", seed: int = 1) -> Path` writing `events.jsonl` and `report.md` into `dir / audit_id` and returning the events path; CLI `python scripts/synthetic_audit.py [--out runs/audits]`.

- [ ] **Step 1: Create the branch**

```bash
git checkout -b m3-ui
```

- [ ] **Step 2: Write `requirements.txt`**: `fastapi`, `uvicorn[standard]`, `httpx`, `pytest`, `pandas`, `numpy`, `scikit-learn`, `yfinance`, `openai`, `anthropic`, `neatlogs`, `opentelemetry-api`, `python-dotenv` (the swarm's existing imports plus the server's). Install only the server set now: `.venv/bin/python -m pip install fastapi "uvicorn[standard]" httpx`.

- [ ] **Step 3: Write the failing tests**

```python
# tests/test_auditor_events.py
import json
from pathlib import Path
from src.auditor.events import EVENT_TYPES, AGENTS, validate_event

def good(**over):
    e = {"seq": 1, "ts": "2026-10-11T12:00:00Z", "audit_id": "a1", "type": "agent_started",
         "agent": "planner", "payload": {"step": "plan"}}
    e.update(over); return e

def test_table_matches_spec():
    assert set(EVENT_TYPES) == {"audit_started", "agent_started", "agent_finished", "llm_call",
        "tool_called", "tool_result", "data_progress", "backtest_result", "check_result",
        "followup_requested", "recovered", "verdict", "report_ready", "error"}
    assert EVENT_TYPES["verdict"] == ("verdict", "reason", "headline", "downgrades")
    assert AGENTS == frozenset({"planner", "researcher", "mathematician", "naysayer", "reporter", "triage"})

def test_valid_event_has_no_problems():
    assert validate_event(good()) == []

def test_problems_are_reported():
    assert validate_event(good(agent="chef"))
    assert validate_event(good(type="nope"))
    assert validate_event(good(payload={}))        # missing "step"
    assert validate_event(good(seq="1"))
    assert validate_event({"type": "verdict"})       # missing keys
    assert validate_event("not a dict")

def test_synthetic_fixture_validates(tmp_path):
    from scripts.synthetic_audit import write_synthetic_audit
    path = write_synthetic_audit(tmp_path)
    events = [json.loads(l) for l in path.read_text().splitlines()]
    assert [e["seq"] for e in events] == list(range(1, len(events) + 1))
    assert all(validate_event(e) == [] for e in events)
    assert events[0]["type"] == "audit_started"
    assert events[0]["payload"]["idea"].startswith("SYNTHETIC FIXTURE")
    assert {e["type"] for e in events} >= {"backtest_result", "followup_requested", "recovered", "verdict", "report_ready", "llm_call"}
    assert (tmp_path / "synthetic-demo" / "report.md").exists()
```

- [ ] **Step 4: Run to verify they fail**: `.venv/bin/python -m pytest tests/test_auditor_events.py -q --basetemp=.pytest_tmp` → ImportError on `src.auditor.events`.

- [ ] **Step 5: Implement `src/auditor/events.py`** with `AGENTS`, `EVENT_TYPES` and `validate_event`. `audit_started` fields: `("idea", "trace_id", "llm_budget", "fault")`; `agent_finished`: `("step", "status", "duration_ms", "summary")`; `llm_call`: `("model", "prompt_tokens", "completion_tokens", "cost_usd", "latency_ms")`; `tool_called`: `("tool", "args")`; `tool_result`: `("tool", "ok", "duration_ms", "summary")`; `data_progress`: `("what", "percent")`; `backtest_result`: `("run", "train", "validation", "baseline", "equity_train", "equity_validation", "histogram")`; `check_result`: `("check", "passed", "value", "note")`; `followup_requested`: `("followup", "reason")`; `recovered`: `("failed", "action", "injected")`; `verdict` as in the test; `report_ready`: `("path", "trace_id", "prose_included")`; `error`: `("step", "message")`.

- [ ] **Step 6: Implement `scripts/synthetic_audit.py`**. Seeded `random.Random(seed)`. Emit, in order: `audit_started` (idea `"SYNTHETIC FIXTURE: buy dips in an uptrend (not a real audit)"`, `trace_id` `"synthetic"`, `llm_budget` 8, `fault` null); planner started → `llm_call` → finished with `summary` `{plan, plan_hash, what_tested}`; researcher started → 3 `tool_called`/`tool_result` pairs with `data_progress` 33/66/100 → one `recovered` (`failed` "dolthub timeout", `action` "halved window and retried", `injected` true) → finished; mathematician started → `backtest_result` run `base` (train and validation stats dicts with every field from the constraint list, `baseline` with the same stats plus `paired_ci_low`, equity curves as lists of `[iso_date, cumulative_return]` with 300 train points and 120 validation points from a random walk, `histogram` as `{"edges": [...], "counts": [...]}`) → finished; naysayer started → `llm_call` → 3 `check_result` → 2 `followup_requested` (F2, F4) → finished; mathematician started → `backtest_result` for F2 and F4 → finished; naysayer started → `llm_call` → finished; `verdict` (`kill`, `reason` "validation mean ≤ 0", `headline` `{n, mean, ci_low, paired_ci_low}` using the base validation numbers, `downgrades` []); reporter started → `llm_call` → `report_ready` (`path` to the written `report.md`, `prose_included` false) → finished. Timestamps start at `2026-10-11T12:00:00Z` and advance 0.2–3.5 s per event so the 2 s cap is exercised. `report.md` content: one heading and the line "Synthetic fixture for UI development. Not a real audit." Every emitted event passes `validate_event` (assert before writing).

- [ ] **Step 7: Run tests**: same command → 4 passed.

- [ ] **Step 8: Generate the dev fixture**: `.venv/bin/python scripts/synthetic_audit.py --out runs/audits` → prints the path `runs/audits/synthetic-demo/events.jsonl`.

- [ ] **Step 9: Commit**

```bash
git add requirements.txt src/auditor/__init__.py src/auditor/events.py scripts/synthetic_audit.py tests/test_auditor_events.py
git commit -m "M3: event contract, validator and synthetic dev fixture generator"
```

### Task 2: Replay helpers

**Files:**
- Create: `src/auditor/replay.py`
- Test: `tests/test_auditor_replay.py`

**Interfaces:**
- Produces: `read_events(path: Path) -> list[dict]` (parses complete lines only: a last line without a trailing newline is skipped; blank lines skipped); `replay_delays(events: list[dict], speed: float, cap_s: float = 2.0) -> list[float]` (delay before each event; first is 0.0; `min(cap_s, ts gap) / speed`; `speed` clamped to 1–8); `find_audit_dir(audit_id: str, roots: list[Path]) -> Path | None` (first root containing `<audit_id>/events.jsonl`; rejects ids containing `/`, `\\` or `..`); `clamp_speed(value) -> float`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_auditor_replay.py
import json
from pathlib import Path
from src.auditor.replay import read_events, replay_delays, find_audit_dir, clamp_speed

def ev(seq, ts): return {"seq": seq, "ts": ts, "audit_id": "a", "type": "x", "agent": None, "payload": {}}

def test_read_events_skips_partial_last_line(tmp_path):
    p = tmp_path / "events.jsonl"
    p.write_text(json.dumps(ev(1, "t")) + "\n\n" + json.dumps(ev(2, "t")) + "\n" + '{"seq": 3, "tru')
    assert [e["seq"] for e in read_events(p)] == [1, 2]

def test_delays_capped_and_scaled():
    events = [ev(1, "2026-10-11T12:00:00Z"), ev(2, "2026-10-11T12:00:00.500Z"), ev(3, "2026-10-11T12:00:10Z")]
    assert replay_delays(events, 1) == [0.0, 0.5, 2.0]
    assert replay_delays(events, 4) == [0.0, 0.125, 0.5]

def test_clamp_speed():
    assert clamp_speed("3") == 3.0
    assert clamp_speed("0") == 1.0 and clamp_speed("99") == 8.0 and clamp_speed("abc") == 1.0 and clamp_speed(None) == 1.0

def test_find_audit_dir(tmp_path):
    runs, results = tmp_path / "runs", tmp_path / "results"
    (results / "demo").mkdir(parents=True); (results / "demo" / "events.jsonl").write_text("")
    assert find_audit_dir("demo", [runs, results]) == results / "demo"
    assert find_audit_dir("nope", [runs, results]) is None
    assert find_audit_dir("../demo", [runs, results]) is None
```

- [ ] **Step 2: Run to verify failure**: `.venv/bin/python -m pytest tests/test_auditor_replay.py -q --basetemp=.pytest_tmp` → ImportError.

- [ ] **Step 3: Implement `src/auditor/replay.py`**. Parse `ts` with `datetime.fromisoformat` after replacing a trailing `Z` with `+00:00`; a malformed `ts` yields a 0.0 gap.

- [ ] **Step 4: Run tests** → 4 passed.

- [ ] **Step 5: Commit**: `git add src/auditor/replay.py tests/test_auditor_replay.py && git commit -m "M3: replay helpers (complete-line reader, capped delays, audit lookup)"`

### Task 3: Server, replay mode

**Files:**
- Create: `src/auditor/server.py`
- Test: `tests/test_auditor_server.py`

**Interfaces:**
- Consumes: Task 2 helpers.
- Produces: `create_app(roots: list[Path] | None = None, ui_dist: Path | None = None, runner: "AuditRunner | None" = None) -> FastAPI`. Defaults: `roots = [REPO/runs/audits, REPO/results/audits]`, `ui_dist = REPO/ui/dist`. Module-level `app = create_app()` for `uvicorn src.auditor.server:app`. Routes:
  - `GET /api/audits` → `[{"audit_id", "idea", "started_at", "finished": bool}]` from each root's `*/events.jsonl` (`idea`/`started_at` from `audit_started`, `finished` true when a `verdict` or `error` event exists), sorted by `started_at` descending, deduplicated by id (first root wins).
  - `GET /api/audits/{id}/events?replay=1&speed=N&from=SEQ` → `text/event-stream`; each event as `id: <seq>\ndata: <original line>\n\n`; `from` (default 0, or the `Last-Event-ID` header) skips events with `seq <= from`; paced by `replay_delays` via `asyncio.sleep`; ends with `event: end\ndata: {}\n\n`. Without `replay=1`: live tail (Task 4). Unknown id → 404.
  - `GET /api/audits/{id}/report` → `text/markdown` body of `report.md`, 404 when the audit or file is missing.
  - If `ui_dist/index.html` exists, mount `StaticFiles(directory=ui_dist, html=True)` at `/` after the API routes.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_auditor_server.py
import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from scripts.synthetic_audit import write_synthetic_audit
from src.auditor.server import create_app

@pytest.fixture
def client(tmp_path):
    write_synthetic_audit(tmp_path / "runs")
    (tmp_path / "ui").mkdir(); (tmp_path / "ui" / "index.html").write_text("<h1>ui</h1>")
    return TestClient(create_app(roots=[tmp_path / "runs", tmp_path / "results"], ui_dist=tmp_path / "ui"))

def sse_events(text):
    return [b for b in text.strip().split("\n\n") if b.startswith("id:")]

def test_replay_streams_every_line_in_order(client, tmp_path):
    lines = (tmp_path / "runs/synthetic-demo/events.jsonl").read_text().splitlines()
    r = client.get("/api/audits/synthetic-demo/events?replay=1&speed=8")
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/event-stream")
    blocks = sse_events(r.text)
    assert [b.split("\n")[1][len("data: "):] for b in blocks] == lines
    assert r.text.rstrip().endswith("event: end\ndata: {}")

def test_replay_from_seq_skips_shown_events(client):
    r = client.get("/api/audits/synthetic-demo/events?replay=1&speed=8&from=5")
    assert sse_events(r.text)[0].startswith("id: 6\n")
    r = client.get("/api/audits/synthetic-demo/events?replay=1&speed=8", headers={"Last-Event-ID": "5"})
    assert sse_events(r.text)[0].startswith("id: 6\n")

def test_bad_speed_clamps(client):
    assert client.get("/api/audits/synthetic-demo/events?replay=1&speed=banana").status_code == 200

def test_unknown_audit_404(client):
    assert client.get("/api/audits/nope/events?replay=1").status_code == 404
    assert client.get("/api/audits/nope/report").status_code == 404

def test_report_and_list(client):
    assert "Synthetic fixture" in client.get("/api/audits/synthetic-demo/report").text
    [a] = client.get("/api/audits").json()
    assert a["audit_id"] == "synthetic-demo" and a["finished"] is True and a["idea"].startswith("SYNTHETIC")

def test_ui_served(client):
    assert "<h1>ui</h1>" in client.get("/").text
```

- [ ] **Step 2: Run to verify failure** → ImportError on `src.auditor.server`.

- [ ] **Step 3: Implement `src/auditor/server.py`** replay routes, list, report, static mount. Use `StreamingResponse(gen(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})` with an async generator. Leave a `runner` parameter and the non-replay branch raising `HTTPException(501, "live mode: Task 4")` for now.

- [ ] **Step 4: Run tests** → 6 passed. Run the whole suite `.venv/bin/python -m pytest tests/ -q --basetemp=.pytest_tmp` and record the count (the `laya` failure is expected).

- [ ] **Step 5: Commit**: `git add src/auditor/server.py tests/test_auditor_server.py && git commit -m "M3: FastAPI server with SSE replay, report and audit list"`

### Task 4: Server, live mode (stretch, small)

**Files:**
- Modify: `src/auditor/server.py`
- Test: `tests/test_auditor_server.py`

**Interfaces:**
- Produces: `class AuditRunner` with `__init__(self, root: Path, command: Callable[[str, str], list[str]] | None = None)` (command builds argv from `(audit_id, idea)`; default `[sys.executable, "-m", "src.auditor", "--id", audit_id, idea]`), `start(self, idea: str) -> str` (new `audit_id` = UTC `%Y%m%d-%H%M%S` plus 4 hex chars; raises `RuntimeError` when one is running), `running: bool`, and a watcher thread that, when the child exits and the file has no `verdict` or `error` event, appends `{"seq": last+1, ..., "type": "error", "agent": null, "payload": {"step": "run", "message": "auditor exited with code N without a verdict"}}`. `POST /api/audits` body `{"idea"}` → `{"audit_id"}`, 409 when running. Live `GET .../events` (no `replay=1`) tails the file (poll every 0.2 s, complete lines only, `from` honoured) and ends after `verdict`/`error` followed by `report_ready`, or after `error`, or 5 s after the child has exited.

- [ ] **Step 1: Add failing tests** using a fake child: `command=lambda aid, idea: [sys.executable, "-c", FAKE]` where `FAKE` writes an `audit_started` line to `root/<aid>/events.jsonl`, sleeps 0.3 s, and exits 0 without a verdict. Tests: `test_post_starts_and_409_while_running`; `test_child_without_verdict_gets_error_event` (poll the file up to 3 s, last event type is `error` with the next seq); `test_live_stream_ends_after_error` (GET without replay returns the two lines and `event: end`).

- [ ] **Step 2: Run to verify failure.** - [ ] **Step 3: Implement.** - [ ] **Step 4: Run tests** → all pass. - [ ] **Step 5: Commit** `"M3: live mode runner (subprocess, 409, watchdog error event)"`.

### Task 5: UI scaffold, event types and the state reducer

**Files:**
- Create: `ui/` via Vite (`package.json`, `vite.config.ts`, `tsconfig*.json`, `index.html`, `src/main.tsx`, `src/index.css`), `ui/src/events.ts`, `ui/src/state.ts`
- Test: `ui/src/state.test.ts`

**Interfaces:**
- Produces: in `events.ts` the discriminated union `AuditEvent` (one interface per type with its payload, `agent: Agent | null`, `Agent = "planner"|"researcher"|"mathematician"|"naysayer"|"reporter"|"triage"`), `Stats` (`n, blocks, win_rate, mean, median, ci_low, ci_high, worst_trade, worst_window`), `EquityPoint = [string, number]`, `Verdict = "kill"|"inconclusive"|"promising"|"cannot_audit"`. In `state.ts`: `type AgentStatus = "idle"|"active"|"done"|"error"`; `interface UiState { phase: "idle"|"running"|"done"; idea: string; startedAt: string|null; traceId: string|null; whatTested: string|null; planHash: string|null; agents: Record<Agent, AgentStatus>; lastAgent: Agent|null; links: {from: Agent, to: Agent, key: number}|null; equityTrain: EquityPoint[]; equityValidation: EquityPoint[]; equityRun: string|null; stats: {train: Stats, validation: Stats, baseline: Stats & {paired_ci_low: number}}|null; followups: {id: string, reason: string}[]; checks: {check: string, passed: boolean, value: unknown, note: string}[]; recoveries: {failed: string, action: string, injected: boolean}[]; verdict: VerdictEvent["payload"]|null; report: {path: string, traceId: string}|null; meters: {llmCalls: number, budget: number, promptTokens: number, completionTokens: number, costUsd: number}; lastSeq: number; errors: string[] }`; `initialState: UiState`; `reduce(state: UiState, event: AuditEvent): UiState` (pure); `agentOrder: Agent[] = ["planner","researcher","mathematician","naysayer","reporter"]`.

- [ ] **Step 1: Scaffold**: from the repo root `npm create vite@latest ui -- --template react-ts`, then in `ui/`: `npm i react@^19 react-dom@^19 framer-motion@^12 lightweight-charts@^5` and `npm i -D typescript@~5.9 vite@^7 @vitejs/plugin-react@^5 tailwindcss@^4 @tailwindcss/vite@^4 vitest@^3`. `vite.config.ts`: plugins `react()`, `tailwindcss()`; `server.proxy = {"/api": "http://127.0.0.1:8000"}`; `build.outDir = "dist"`. `package.json` scripts: `dev`, `build` (`tsc -b && vite build`), `test` (`vitest run`), `typecheck` (`tsc -b --noEmit`). Add `ui/node_modules/` and `ui/dist/` to `.gitignore`. Delete the template's `App.css` and asset files.

- [ ] **Step 2: Write `ui/src/events.ts`** types per the Interfaces block.

- [ ] **Step 3: Write failing reducer tests**

```ts
// ui/src/state.test.ts
import { describe, it, expect } from "vitest";
import { initialState, reduce } from "./state";
import type { AuditEvent } from "./events";
const base = { ts: "2026-10-11T12:00:00Z", audit_id: "a" };
const ev = (seq: number, e: object) => ({ seq, ...base, ...e }) as AuditEvent;

describe("reduce", () => {
  it("audit_started sets idea, date, trace and phase", () => {
    const s = reduce(initialState, ev(1, { type: "audit_started", agent: null, payload: { idea: "x", trace_id: "t", llm_budget: 8, fault: null } }));
    expect(s).toMatchObject({ phase: "running", idea: "x", startedAt: base.ts, traceId: "t", meters: { budget: 8 }, lastSeq: 1 });
  });
  it("agent start/finish drive statuses and a link from the previous agent", () => {
    let s = reduce(initialState, ev(1, { type: "agent_started", agent: "planner", payload: { step: "plan" } }));
    expect(s.agents.planner).toBe("active");
    s = reduce(s, ev(2, { type: "agent_finished", agent: "planner", payload: { step: "plan", status: "ok", duration_ms: 1, summary: { what_tested: "W", plan_hash: "H" } } }));
    expect(s.agents.planner).toBe("done"); expect(s.whatTested).toBe("W"); expect(s.planHash).toBe("H");
    s = reduce(s, ev(3, { type: "agent_started", agent: "researcher", payload: { step: "data" } }));
    expect(s.links).toMatchObject({ from: "planner", to: "researcher" });
  });
  it("followup_requested animates naysayer -> mathematician", () => {
    const s = reduce(initialState, ev(1, { type: "followup_requested", agent: "naysayer", payload: { followup: "F2", reason: "r" } }));
    expect(s.followups).toEqual([{ id: "F2", reason: "r" }]); expect(s.links).toMatchObject({ from: "naysayer", to: "mathematician" });
  });
  it("llm_call accumulates meters", () => {
    const call = { type: "llm_call", agent: "planner", payload: { model: "m", prompt_tokens: 10, completion_tokens: 5, cost_usd: 0.01, latency_ms: 1 } };
    const s = reduce(reduce(initialState, ev(1, call)), ev(2, call));
    expect(s.meters).toMatchObject({ llmCalls: 2, promptTokens: 20, completionTokens: 10 }); expect(s.meters.costUsd).toBeCloseTo(0.02);
  });
  it("only the base run feeds the equity curves and stats", () => {
    const stats = { n: 1, blocks: 1, win_rate: 0, mean: 0, median: 0, ci_low: 0, ci_high: 0, worst_trade: 0, worst_window: 0 };
    const bt = (run: string, pts: [string, number][]) => ev(1, { type: "backtest_result", agent: "mathematician", payload: { run, train: stats, validation: stats, baseline: { ...stats, paired_ci_low: 0 }, equity_train: pts, equity_validation: pts, histogram: {} } });
    let s = reduce(initialState, bt("base", [["2025-01-02", 0.1]]));
    s = reduce(s, bt("F2", [["2025-01-02", 9]]));
    expect(s.equityTrain).toEqual([["2025-01-02", 0.1]]); expect(s.equityRun).toBe("base");
  });
  it("verdict without backtests still shows", () => {
    const s = reduce(initialState, ev(1, { type: "verdict", agent: null, payload: { verdict: "cannot_audit", reason: "refused", headline: {}, downgrades: [] } }));
    expect(s.phase).toBe("done"); expect(s.verdict?.verdict).toBe("cannot_audit"); expect(s.equityTrain).toEqual([]);
  });
  it("recovered and error are kept", () => {
    let s = reduce(initialState, ev(1, { type: "recovered", agent: "researcher", payload: { failed: "f", action: "a", injected: true } }));
    s = reduce(s, ev(2, { type: "error", agent: null, payload: { step: "run", message: "boom" } }));
    expect(s.recoveries[0].injected).toBe(true); expect(s.errors).toEqual(["run: boom"]); expect(s.phase).toBe("done");
  });
});
```

- [ ] **Step 4: Run** `cd ui && npm test` → fails (no `./state`).

- [ ] **Step 5: Implement `ui/src/state.ts`**. `agent_finished` with `status: "error"` sets the agent to `"error"`. `report_ready` sets `report` and `reporter` to done. `links` gets a fresh `key` (incrementing number) on every change so the graph can re-run its animation.

- [ ] **Step 6: Run** `npm test` → 7 passed; `npm run typecheck` → clean.

- [ ] **Step 7: Commit**: `git add .gitignore ui && git commit -m "M3: UI scaffold (Vite, React, Tailwind), event types and state reducer"`

### Task 6: Stream client, replay controls and the command bar

**Files:**
- Create: `ui/src/stream.ts`, `ui/src/useAudit.ts`, `ui/src/components/CommandBar.tsx`, `ui/src/components/ReplayControls.tsx`, `ui/src/App.tsx` (replace template), `ui/src/index.css` (replace)

**Interfaces:**
- Produces: `stream.ts`: `openEvents(auditId: string, opts: {replay: boolean, speed: number, from: number, onEvent: (e: AuditEvent) => void, onEnd: () => void, onError: (msg: string) => void}): () => void` (returns a close function; uses `EventSource` on `/api/audits/${id}/events?...`; listens for the `end` event). `listAudits(): Promise<AuditSummary[]>` (`AuditSummary = {audit_id: string, idea: string, started_at: string, finished: boolean}`). `fetchReport(id): Promise<string>`.
  `useAudit.ts`: hook `useAudit(): { state: UiState, audits: AuditSummary[], mode: "replay"|"live", speed: number, setSpeed, playing: boolean, play(auditId: string), pause(), resume(), reset(), currentAuditId: string|null, submitIdea(text: string): void }`. `submitIdea` in replay mode finds the first audit whose idea, lower-cased, contains the text lower-cased (and vice versa) and plays it, else sets `state.errors` to `["No recording for this idea. Record one with the auditor first."]`. `resume()` reopens from `state.lastSeq`. `setSpeed` while playing reopens from `lastSeq` at the new speed.
  `CommandBar` props `{ state, audits, mode, onSubmit(text), onChip(text), chips: string[], startedAt: string|null }`: input, the three chips (constant `DEMO_IDEAS` in `App.tsx`, exact spec text), a LIVE/REPLAY pill (REPLAY shows "REPLAY · <original run date, YYYY-MM-DD HH:MM UTC>"), and the "What was tested" line once `state.whatTested` is set (with the plan hash's first 12 chars in mono).
  `ReplayControls` props `{ playing, speed, onPlay, onPause, onSpeed, disabled }`: play/pause button and speed buttons 1, 2, 4, 8.

- [ ] **Step 1: Write `index.css`**: `@import "tailwindcss";` then `@theme { --font-sans: "IBM Plex Sans", system-ui, sans-serif; --font-mono: "JetBrains Mono", ui-monospace, monospace; --color-bg: #0b0e13; --color-panel: #11161e; --color-line: #1f2733; --color-text: #e6edf3; --color-muted: #8b98a8; --color-accent: #4cc9f0; --color-kill: #ef4444; --color-inconclusive: #f59e0b; --color-promising: #22c55e; --color-cannot: #6b7280; }`, `body { background: var(--color-bg); color: var(--color-text); }`, and `@media (prefers-reduced-motion: reduce) { *, *::before, *::after { animation-duration: 0.01ms !important; transition-duration: 0.01ms !important; } }`. Google Fonts `<link>` for IBM Plex Sans 400/500/600 and JetBrains Mono 400/600 in `index.html`; `<title>Strategy Auditor</title>`.

- [ ] **Step 2: Implement `stream.ts`, `useAudit.ts`, `CommandBar.tsx`, `ReplayControls.tsx`, and `App.tsx`** with the 1920×1080 grid: command bar full width (row 1), agent graph left and evidence right (row 2), verdict full width (row 3), footer meters (row 4). Placeholders for graph, curves, stamp and meters are plain `<section>` boxes with their titles until Tasks 7–9 replace them. Framer Motion's `useReducedMotion()` is read once in `App` and passed down as `reduced: boolean`.

- [ ] **Step 3: Manual check**: terminal 1 `.venv/bin/python -m uvicorn src.auditor.server:app --port 8000`; terminal 2 `cd ui && npm run dev`. Open the dev URL: the chip "buy dips in an uptrend" plays `synthetic-demo` (its idea contains the chip text), the REPLAY pill shows `2026-10-11 12:00 UTC`, the "What was tested" line appears after the planner finishes, pause stops new lines, resume continues without repeats (check `lastSeq` in React DevTools or a temporary console log).

- [ ] **Step 4: `npm run typecheck && npm test`** → clean. **Commit**: `"M3: SSE client, replay controls and command bar"`

### Task 7: Agent graph

**Files:**
- Create: `ui/src/components/AgentGraph.tsx`

**Interfaces:**
- Consumes: `state.agents`, `state.lastAgent`, `state.links`, `state.followups.length`, `state.recoveries`, `reduced`.
- Produces: `AgentGraph({ state, reduced }: { state: UiState, reduced: boolean })`.

- [ ] **Step 1: Implement**: an SVG (`viewBox 0 0 760 420`) with five nodes in the section 4 loop order laid out left to right: Planner → Researcher → Mathematician → Naysayer → Reporter, plus a return arc Naysayer → Mathematician labelled "follow-ups ×N". Node: rounded rect, name in sans, step label in mono under it, status ring: idle `--color-line`, active `--color-accent` with a 400 ms scale-in and a glow (`filter: drop-shadow`) held while active (a held state, not a loop), done `--color-promising` outline, error `--color-kill`. Links: a `motion.circle` travelling along the link path for 500 ms when `state.links.key` changes (`key={links.key}` to restart). A small badge on Researcher listing recoveries as `REAL` or `INJECTED`. With `reduced`, the travelling dot and glow are replaced by an instant colour change.

- [ ] **Step 2: Manual check** in the replay: nodes light in order, the dot travels on each handoff, the return arc animates twice for F2 and F4, the INJECTED badge appears on Researcher.

- [ ] **Step 3: `npm run typecheck`** clean. **Commit**: `"M3: agent graph with per-event handoff animation"`

### Task 8: Equity curves

**Files:**
- Create: `ui/src/components/EquityCurves.tsx`
- Test: `ui/src/components/equitySeries.test.ts`, create `ui/src/components/equitySeries.ts`

**Interfaces:**
- Produces: `toSeries(points: EquityPoint[]): {time: string, value: number}[]` (drops points whose date is not `YYYY-MM-DD` or whose value is not finite; sorts ascending by time; removes duplicate times keeping the last). `EquityCurves({ state, reduced })` renders two `lightweight-charts` line series (train in `--color-muted`, validation in `--color-accent`) on one chart with a dark theme (`layout.background` solid `--color-panel`, grid lines `--color-line`, `rightPriceScale`), a legend "TRAIN n=… mean=…" / "VALIDATION n=… mean=… CI [lo, hi]" from `state.stats`, and a baseline strip under the chart: validation mean vs no-condition baseline mean as two horizontal bars with the paired lower bound as a mono figure. The "draw-in" effect: on new data, the series are fed point by point over 600 ms with `requestAnimationFrame` (whole series at once when `reduced`).

- [ ] **Step 1: Failing tests** for `toSeries`: empty input → `[]`; an unsorted input is sorted; `["bad", 1]` and `["2025-01-02", NaN]` dropped; duplicate `2025-01-02` keeps the last value.

- [ ] **Step 2: Run** `npm test` → fails. **Step 3: Implement `equitySeries.ts`.** **Step 4: `npm test`** → passes.

- [ ] **Step 5: Implement `EquityCurves.tsx`** with `createChart` in a `useEffect`, `chart.addSeries(LineSeries, {...})` (v5 API), `ResizeObserver` for width, `chart.remove()` on unmount. Empty series → the chart stays empty and a muted "waiting for backtest" caption shows.

- [ ] **Step 6: Manual check**: the base run draws both curves; the F2/F4 results do not redraw them; the panel at 1280 px wide still shows the legend without overflow.

- [ ] **Step 7: Commit**: `"M3: train vs validation equity curves (lightweight-charts) with baseline strip"`

### Task 9: Verdict stamp and footer meters

**Files:**
- Create: `ui/src/components/VerdictStamp.tsx`, `ui/src/components/FooterMeters.tsx`, `ui/src/components/countUp.ts`

**Interfaces:**
- Produces: `countUp(from: number, to: number, ms: number, onFrame: (v: number) => void): () => void` (rAF, cancel function; jumps straight to `to` when `ms <= 0`). `VerdictStamp({ state, reduced, reportUrl, traceUrl })` and `FooterMeters({ state, elapsedMs, followupsRun })`.

- [ ] **Step 1: Implement `VerdictStamp`**: before the verdict, a low-contrast empty band with "VERDICT PENDING". On `state.verdict`, a full-width stamp: label `KILLED` / `INCONCLUSIVE` / `PROMISING` / `CANNOT AUDIT` with its colour, 900 ms reveal (scale from 1.15 and rotate from -3° to 0, opacity in; just opacity when `reduced`), the reason line, headline figures `n`, `mean`, `lower bound`, `paired lower bound` counting up over 900 ms from 0 using `countUp` (format: `n` integer, the others as `+0.00%`), subtitles exactly as the Global Constraints state for PROMISING and INCONCLUSIVE, the downgrade list when non-empty, and two links: "Report" (`/api/audits/<id>/report`, opens in a new tab) and "neatlogs trace" (disabled with the title "trace URL format to be verified" until `traceUrl` is a string). `cannot_audit` hides the figures and shows only the reason.

- [ ] **Step 2: Implement `FooterMeters`**: elapsed (`mm:ss` from `elapsedMs`, computed in `App` from the first and the latest event `ts`, not wall-clock, so replay speed does not distort it), `LLM calls k / 8`, tokens (prompt + completion, thousands separator), cost (`$0.0000`), follow-ups run (count of `backtest_result` events whose `run` starts with `F`; add `followupsRun: number` to `UiState` and the reducer, with a reducer test).

- [ ] **Step 3: Wire both into `App.tsx`**, removing the placeholders. **`npm run typecheck && npm test`** clean.

- [ ] **Step 4: Manual check**: the stamp lands after the verdict event; figures count up; a reload and replay at 8× still ends on the same numbers.

- [ ] **Step 5: Commit**: `"M3: verdict stamp with count-up headline and footer meters"`

### Task 10: Production build, served by the server, screen checks, docs

**Files:**
- Modify: `docs/STATUS.md` (M3 row and "Running things"), `README.md` (a "Mission control" section)
- Build: `ui/dist` (gitignored)

- [ ] **Step 1:** `cd ui && npm run build` → `dist/index.html` exists; `npm run typecheck` and `npm test` clean.

- [ ] **Step 2:** `.venv/bin/python -m uvicorn src.auditor.server:app --port 8000`, open `http://127.0.0.1:8000/` in the browser preview; play the synthetic replay at 1×, 4× and 8×.

- [ ] **Step 3: Screen checks** at 1920×1080 and 1280×800: no horizontal scroll, every panel visible without scrolling at 1920×1080, the verdict stamp readable in both. Fix layout issues found.

- [ ] **Step 4: Full test suite**: `.venv/bin/python -m pytest tests/ -q --basetemp=.pytest_tmp` → all new tests pass (the `laya` failure is pre-existing).

- [ ] **Step 5: Docs**: in `docs/STATUS.md` add a row "Mission-control UI (M3)" stating: built in replay mode against the section 16 contract, verified only with the synthetic fixture (`scripts/synthetic_audit.py`, never for recording), and that it waits for M1's real `events.jsonl` in `results/audits/`. Under "Running things" add the two commands (server, UI dev) and the build command. In `README.md` add the same three commands.

- [ ] **Step 6: Commit**: `git add docs/STATUS.md README.md && git commit -m "M3: docs for running the mission-control replay UI"` and push the branch: `git push -u origin m3-ui`.
