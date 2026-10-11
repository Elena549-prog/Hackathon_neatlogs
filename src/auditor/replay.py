"""Replay helpers for the mission-control server (AUDITOR_SPEC.md section 16).

Reads complete lines of an events.jsonl, paces a replay from the event timestamps (gaps capped
at 2 s, divided by the speed), and finds an audit directory under the allowed roots.
"""
import datetime as dt
import json
from pathlib import Path

GAP_CAP_S = 2.0
MIN_SPEED, MAX_SPEED = 1.0, 8.0


def read_event_lines(path):
    """(raw line, parsed event) for each complete line. A trailing line without a newline is skipped."""
    text = Path(path).read_text(encoding="utf-8")
    if text and not text.endswith("\n"):
        text = text[:text.rfind("\n") + 1]
    out = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except ValueError:
            continue        # a corrupt line must not kill a replay; it is skipped like a partial one
        if isinstance(event, dict):
            out.append((line, event))
    return out


def event_seq(event):
    """The event's seq as an int, or None when missing or unparsable."""
    try:
        return int(event["seq"])
    except (KeyError, TypeError, ValueError):
        return None


def read_events(path):
    """Parse the complete lines of an events file."""
    return [event for _, event in read_event_lines(path)]


def clamp_speed(value):
    """Speed 1–8 as a float; anything unparsable becomes 1."""
    try:
        speed = float(value)
    except (TypeError, ValueError):
        return MIN_SPEED
    if speed != speed:      # NaN
        return MIN_SPEED
    return max(MIN_SPEED, min(MAX_SPEED, speed))


def _parse_ts(value):
    """Aware datetime, or None. A naive timestamp is taken as UTC so gaps never mix naive and aware."""
    try:
        ts = dt.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return ts if ts.tzinfo else ts.replace(tzinfo=dt.timezone.utc)


def replay_delays(events, speed, cap_s=GAP_CAP_S):
    """Seconds to wait before each event: min(cap, gap to the previous event) / speed."""
    speed = clamp_speed(speed)
    delays, previous = [], None
    for event in events:
        ts = _parse_ts(event.get("ts"))
        try:
            gap = (ts - previous).total_seconds() if ts and previous else 0.0
        except TypeError:
            gap = 0.0
        delays.append(min(cap_s, max(0.0, gap)) / speed)
        previous = ts or previous
    return delays


def find_audit_dir(audit_id, roots):
    """First root holding <audit_id>/events.jsonl, or None. Rejects path-like ids."""
    if not audit_id or any(bad in audit_id for bad in ("/", "\\", "..")):
        return None
    for root in roots:
        candidate = Path(root) / audit_id
        if (candidate / "events.jsonl").is_file():
            return candidate
    return None
