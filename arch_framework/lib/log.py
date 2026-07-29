"""Logging with the same visual vocabulary as the Bash implementation.

Everything goes to stderr. Stdout is reserved for data a caller might capture,
which is the mistake the Bash version made and had to be corrected for.
"""

from __future__ import annotations

import os
import sys
from enum import Enum


class Level(Enum):
    INFO = ("INFO", "\033[0;34m")
    OK = ("OK", "\033[0;32m")
    WARN = ("WARN", "\033[0;33m")
    ERROR = ("ERROR", "\033[0;31m")

    def __init__(self, label: str, colour: str) -> None:
        self.label = label
        self.colour = colour


_RESET = "\033[0m"
_BOLD = "\033[1m"


def _colour_enabled() -> bool:
    if os.environ.get("NO_COLOR"):
        return False
    return sys.stderr.isatty()


def _emit(level: Level, message: str) -> None:
    if _colour_enabled():
        prefix = f"{level.colour}[{level.label}]{_RESET}"
    else:
        prefix = f"[{level.label}]"

    print(f"{prefix} {message}", file=sys.stderr)


def info(message: str) -> None:
    _emit(Level.INFO, message)


def success(message: str) -> None:
    _emit(Level.OK, message)


def warn(message: str) -> None:
    _emit(Level.WARN, message)


def error(message: str) -> None:
    _emit(Level.ERROR, message)


def section(title: str) -> None:
    if _colour_enabled():
        print(f"\n{_BOLD}{title}{_RESET}", file=sys.stderr)
    else:
        print(f"\n{title}", file=sys.stderr)
