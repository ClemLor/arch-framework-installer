"""The progress protocol, read side.

Mirrors ``lib/events.sh``. Deliberately nothing but parsing: no files, no
processes, so it is testable from hand-written records and a malformed line has
one obvious place to be rejected.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

#: First field of every record. A future format gets a new tag rather than a
#: silently different meaning for the same one.
PROTOCOL_TAG = "AFI1"


@dataclass(frozen=True)
class Event:
    kind: str
    fields: Mapping[str, str] = field(default_factory=dict)
    raw: str = ""

    def get(self, key: str, default: str = "") -> str:
        return self.fields.get(key, default)

    def integer(self, key: str, default: int = 0) -> int:
        try:
            return int(self.fields[key])
        except (KeyError, ValueError):
            return default

    def flag(self, key: str) -> bool:
        return self.fields.get(key, "false") == "true"


def parse_line(line: str) -> Event | None:
    """One record, or None for anything that is not one.

    Returning None rather than raising is what lets the caller read a stream that
    also carries ordinary output: a line it does not recognise is not an error,
    it is not an event.
    """
    stripped = line.rstrip("\n").rstrip("\r")
    if not stripped:
        return None

    parts = stripped.split("\t")
    if len(parts) < 2 or parts[0] != PROTOCOL_TAG:
        return None

    kind = parts[1]
    if not kind:
        return None

    fields: dict[str, str] = {}
    for part in parts[2:]:
        # Split once: a value is allowed to contain '='.
        key, separator, value = part.partition("=")
        if separator and key:
            fields[key] = value

    return Event(kind=kind, fields=fields, raw=stripped)
