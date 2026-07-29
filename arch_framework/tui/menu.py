"""The menu as data.

Both renderers walk the same registry, so an entry is added once and appears in
the Textual interface and in the plain-prompt fallback with no duplicated
layout code. This mirrors how archinstall keeps its global menu separate from
its widgets.

Each entry knows how to read its current value out of the configuration and how
to render it as a single line, because that inline current-value column is what
makes an archinstall-style menu readable at a glance.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any

NOT_SET = "(not set)"


class Action(Enum):
    """What the renderer should do when the user leaves the menu."""

    CONTINUE = auto()
    SAVE = auto()
    INSTALL = auto()
    ABORT = auto()


@dataclass
class MenuEntry:
    """One configurable line in the menu."""

    key: str
    label: str
    #: Reads the display value from the configuration. Returns NOT_SET when the
    #: entry has not been answered yet.
    preview: Callable[[Any], str]
    #: Runs the entry's own interaction and mutates the configuration.
    edit: Callable[[Any], None] | None = None
    #: Mandatory entries block Install until answered, and are marked in the
    #: display.
    mandatory: bool = False
    #: Longer text shown alongside the entry to help the user decide.
    help_text: str = ""

    def is_answered(self, config: Any) -> bool:
        return self.preview(config) != NOT_SET


@dataclass
class MenuRegistry:
    entries: list[MenuEntry] = field(default_factory=list)

    def add(self, entry: MenuEntry) -> "MenuRegistry":
        self.entries.append(entry)
        return self

    def get(self, key: str) -> MenuEntry | None:
        return next((entry for entry in self.entries if entry.key == key), None)

    def unanswered_mandatory(self, config: Any) -> list[MenuEntry]:
        return [
            entry
            for entry in self.entries
            if entry.mandatory and not entry.is_answered(config)
        ]

    def render_lines(self, config: Any) -> list[str]:
        """Aligned ``label ... value`` lines, with mandatory entries marked."""
        width = max((len(entry.label) for entry in self.entries), default=0) + 2
        lines: list[str] = []
        for entry in self.entries:
            marker = " *" if entry.mandatory else "  "
            label = f"{entry.label}{marker}".ljust(width + 2, ".")
            lines.append(f"{label} {entry.preview(config)}")
        return lines
