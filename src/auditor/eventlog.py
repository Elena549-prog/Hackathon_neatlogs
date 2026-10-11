"""Append-only writer for runs/audits/<audit_id>/events.jsonl (AUDITOR_SPEC section 16).

Every event is validated against the contract before it is written; seq continues across --resume.
"""
import datetime as dt
import json
from pathlib import Path

from .events import validate_event
from .replay import read_events


def utc_now():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


class EventLog:
    def __init__(self, path, audit_id, start_seq=0):
        self.path, self.audit_id, self.seq = Path(path), audit_id, start_seq
        self.path.parent.mkdir(parents=True, exist_ok=True)

    @classmethod
    def resume(cls, path, audit_id):
        """Continue after the last complete line of an existing file."""
        path = Path(path)
        last = max((int(e.get("seq", 0)) for e in read_events(path)), default=0) if path.is_file() else 0
        return cls(path, audit_id, start_seq=last)

    def emit(self, type_, agent, payload):
        event = {"seq": self.seq + 1, "ts": utc_now(), "audit_id": self.audit_id,
                 "type": type_, "agent": agent, "payload": payload}
        problems = validate_event(event)
        if problems:
            raise ValueError("invalid %s event: %s" % (type_, "; ".join(problems)))
        line = json.dumps(event, default=_json_default)
        with self.path.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
            f.flush()
        self.seq = event["seq"]
        return event


def _json_default(value):
    """numpy scalars, pandas timestamps, paths and sets become plain JSON."""
    if hasattr(value, "item"):
        return value.item()
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if isinstance(value, (set, frozenset)):
        return sorted(value)
    return str(value)
