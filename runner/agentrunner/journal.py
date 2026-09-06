"""An append-only record of what the run did and what it refused.

A refusal that leaves no trace is indistinguishable from an action that never
happened. The journal is JSONL so it can be read by `tail -f` during a run and
by a test afterwards.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class Entry:
    event: str
    at: str = ""
    detail: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.at = self.at or datetime.now(timezone.utc).isoformat(timespec="seconds")


class Journal:
    def __init__(self, path: Path | None = None, echo: bool = True) -> None:
        self.path = path
        self.echo = echo
        self.entries: list[Entry] = []
        if path:
            path.parent.mkdir(parents=True, exist_ok=True)

    def record(self, event: str, **detail) -> Entry:
        entry = Entry(event=event, detail=detail)
        self.entries.append(entry)
        line = json.dumps(asdict(entry), ensure_ascii=False)
        if self.path:
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(line + "\n")
        if self.echo:
            print(self._human(entry), flush=True)
        return entry

    def events(self, event: str) -> list[Entry]:
        return [e for e in self.entries if e.event == event]

    @staticmethod
    def _human(entry: Entry) -> str:
        marks = {"refused": "✗", "verified": "✓", "verify_failed": "✗", "executed": "→"}
        mark = marks.get(entry.event, "·")
        detail = " ".join(f"{k}={v}" for k, v in entry.detail.items() if k != "traceback")
        return f"{mark} {entry.event} {detail}".rstrip()
