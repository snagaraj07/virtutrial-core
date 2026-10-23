"""Append-only JSONL audit log.

The store exposes ``append_event`` and ``list_events``. There is no function
that updates or deletes a past line.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

AUDIT_KEYS = ("ts", "actor", "action", "study_id", "run_id")
ACTIONS = frozenset(
    {
        "run.created",
        "run.executed",
        "report.exported",
        "predictions.exported",
        "study.deleted",
    }
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def append_event(path: Path, event: dict) -> None:
    """Append one JSON object and a newline. Do not rewrite the file."""

    missing = [key for key in AUDIT_KEYS if key not in event]
    if missing:
        raise ValueError(f"Audit event is missing {', '.join(missing)}.")
    action = str(event["action"])
    if action not in ACTIONS:
        raise ValueError("Unknown audit action.")
    record = {key: event[key] for key in AUDIT_KEYS}
    record["ts"] = str(record["ts"])
    record["actor"] = str(record["actor"])
    record["action"] = action
    record["study_id"] = str(record["study_id"])
    record["run_id"] = str(record["run_id"])
    dest = Path(path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(record, separators=(",", ":"), ensure_ascii=True)
    with dest.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")


def list_events(path: Path) -> list[dict]:
    """Return the audit lines in file order. Missing file is an empty list."""

    dest = Path(path)
    if not dest.is_file():
        return []
    events = []
    for raw in dest.read_text(encoding="utf-8").splitlines():
        if not raw.strip():
            continue
        events.append(json.loads(raw))
    return events
