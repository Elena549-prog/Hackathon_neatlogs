"""Audit event contract (AUDITOR_SPEC.md section 16).

One JSON object per line in runs/audits/<audit_id>/events.jsonl:
{"seq", "ts", "audit_id", "type", "agent", "payload"}. `agent` is null for audit-level events.
"""

AGENTS = frozenset({"planner", "researcher", "mathematician", "naysayer", "reporter", "triage"})

TOP_LEVEL = ("seq", "ts", "audit_id", "type", "agent", "payload")

# type -> required payload fields, copied from the section 16 table.
EVENT_TYPES = {
    "audit_started": ("idea", "trace_id", "llm_budget", "fault"),
    "agent_started": ("step",),
    "agent_finished": ("step", "status", "duration_ms", "summary"),
    "llm_call": ("model", "prompt_tokens", "completion_tokens", "cost_usd", "latency_ms"),
    "tool_called": ("tool", "args"),
    "tool_result": ("tool", "ok", "duration_ms", "summary"),
    "data_progress": ("what", "percent"),
    "backtest_result": ("run", "train", "validation", "baseline",
                        "equity_train", "equity_validation", "histogram"),
    "check_result": ("check", "passed", "value", "note"),
    "followup_requested": ("followup", "reason"),
    "recovered": ("failed", "action", "injected"),
    "verdict": ("verdict", "reason", "headline", "downgrades"),
    "report_ready": ("path", "trace_id", "prose_included"),
    "error": ("step", "message"),
}


def validate_event(obj):
    """Return a list of problems; an empty list means the event is valid."""
    if not isinstance(obj, dict):
        return ["event is not an object"]
    problems = ["missing key %r" % k for k in TOP_LEVEL if k not in obj]
    if problems:
        return problems
    if not isinstance(obj["seq"], int) or isinstance(obj["seq"], bool):
        problems.append("seq must be an integer")
    if not isinstance(obj["ts"], str):
        problems.append("ts must be a string")
    if obj["agent"] is not None and obj["agent"] not in AGENTS:
        problems.append("unknown agent %r" % (obj["agent"],))
    if obj["type"] not in EVENT_TYPES:
        problems.append("unknown type %r" % (obj["type"],))
    elif not isinstance(obj["payload"], dict):
        problems.append("payload must be an object")
    else:
        problems += ["payload of %s missing %r" % (obj["type"], f)
                     for f in EVENT_TYPES[obj["type"]] if f not in obj["payload"]]
    return problems
