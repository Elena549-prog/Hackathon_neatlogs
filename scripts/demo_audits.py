"""Demo audits for the video and the before/after evidence (AUDITOR_SPEC sections 8, 13, 17).

    python scripts/demo_audits.py before    # the three demo ideas with --no-followups (M1 behaviour)
    python scripts/demo_audits.py after     # the same three ideas with follow-ups F1-F4 (M2)
    python scripts/demo_audits.py fault     # idea 2 with --fault dolthub_timeout (the labelled recovery beat)
    python scripts/demo_audits.py table     # results/audits/before_after.md from the copied runs

Each audit is a real DeepSeek run (`python -m src.auditor`, balance check included). Its events.jsonl, report.md
and state.json are copied to results/audits/<id>/ so they can be committed and replayed by the UI. An id that
already exists under results/audits/ is never overwritten. 7 audits in all, under the 25-audit cap.
"""
import datetime as dt
import json
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
RUNS, RESULTS = REPO / "runs" / "audits", REPO / "results" / "audits"
# Written into the spec (section 13) before any run, with the expected verdicts.
IDEAS = [("dips", "buy dips in an uptrend", "kill"),
         ("straddle-buy", "buy straddles on tech before earnings", "kill"),
         ("straddle-sell", "sell straddles on low-volatility mega-caps", "inconclusive or promising (tail risk decides)")]
COPY = ("events.jsonl", "report.md", "state.json")


def run(audit_id, idea, *flags):
    dest = RESULTS / audit_id
    if dest.exists():
        print("skip %s: %s already exists (delete it by hand to redo)" % (audit_id, dest))
        return
    cmd = [sys.executable, "-m", "src.auditor", "--id", audit_id, *flags, idea]
    print("$ " + " ".join(cmd), flush=True)
    if subprocess.run(cmd, cwd=REPO).returncode != 0:
        sys.exit("audit %s failed; finish it with: python -m src.auditor --resume %s" % (audit_id, audit_id))
    dest.mkdir(parents=True)
    for name in COPY:
        shutil.copy2(RUNS / audit_id / name, dest / name)
    print("copied to %s" % dest)


def _wall_seconds(events_path):
    ev = [json.loads(l) for l in events_path.read_text(encoding="utf-8").splitlines() if l.strip()]
    ts = [dt.datetime.fromisoformat(e["ts"].replace("Z", "+00:00")) for e in ev]
    return (ts[-1] - ts[0]).total_seconds() if ts else 0.0


def row(audit_id):
    d = RESULTS / audit_id
    if not (d / "state.json").is_file():
        return None
    st = json.loads((d / "state.json").read_text(encoding="utf-8"))
    steps = st["steps"]
    v = steps["verdict"]["result"]
    runs = steps.get("followups", {}).get("result", {}).get("runs", [])
    met = ["%s (%s)" % (r["id"], "met" if r["downgrade"] else "not met") for r in runs]
    return {"verdict": v["verdict"], "downgrades": "; ".join(x["cause"] for x in v["downgrades"]) or "none",
            "followups": ", ".join(met) or "none", "calls": st["llm_calls"], "usd": st["cost"]["usd"],
            "wall": _wall_seconds(d / "events.jsonl")}


def table():
    lines = ["# Strategy Auditor: before (M1, no follow-ups) vs after (M2, follow-ups F1-F4)", "",
             "Metrics fixed in AUDITOR_SPEC section 17 before any run: verdict per idea, downgrades with reasons, "
             "LLM calls, cost and wall time per audit. Expected verdicts were written in section 13 first. "
             "Cost is the wrapper's upper bound; check it against the neatlogs traces.", "",
             "| Idea | Expected | Run | Verdict | Downgrades | Follow-ups (rule) | LLM calls | Cost | Wall time |",
             "|---|---|---|---|---|---|---|---|---|"]
    for slug, idea, expected in IDEAS:
        for when in ("before", "after"):
            r = row("%s-%s" % (when, slug))
            if r is None:
                lines.append("| %s | %s | %s | not run yet | | | | | |" % (idea, expected, when))
                continue
            lines.append("| %s | %s | %s | %s | %s | %s | %d | $%.4f | %.0f s |" % (
                idea, expected, when, r["verdict"], r["downgrades"], r["followups"], r["calls"], r["usd"], r["wall"]))
    out = RESULTS / "before_after.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    print("\nwritten to %s" % out)


def main(argv=None):
    mode = (argv or sys.argv[1:] or [""])[0]
    if mode in ("before", "after"):
        for slug, idea, _ in IDEAS:
            run("%s-%s" % (mode, slug), idea, *(["--no-followups"] if mode == "before" else []))
        table()
    elif mode == "fault":
        run("fault-dolthub", IDEAS[1][1], "--fault", "dolthub_timeout")
    elif mode == "table":
        table()
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
