"""What a keypress means.

Keys arrive as symbol strings — ``"DOWN"``, ``"ENTER"``, ``"j"`` — never as the
integers curses returns. That keeps this module free of curses (so it is testable
anywhere) and keeps ``258`` out of the code that decides what to do.
"""

from __future__ import annotations

from enum import Enum, auto


class Command(Enum):
    MOVE_UP = auto()
    MOVE_DOWN = auto()
    PAGE_UP = auto()
    PAGE_DOWN = auto()
    HOME = auto()
    END = auto()
    EDIT = auto()
    SAVE = auto()
    INSTALL = auto()
    QUIT = auto()
    HELP = auto()
    REDRAW = auto()
    RESIZE = auto()
    NONE = auto()


_MAIN: dict[str, Command] = {
    "UP": Command.MOVE_UP,
    "k": Command.MOVE_UP,
    "DOWN": Command.MOVE_DOWN,
    "j": Command.MOVE_DOWN,
    "PPAGE": Command.PAGE_UP,
    "NPAGE": Command.PAGE_DOWN,
    "HOME": Command.HOME,
    "END": Command.END,
    "ENTER": Command.EDIT,
    " ": Command.EDIT,
    "RIGHT": Command.EDIT,
    "s": Command.SAVE,
    "i": Command.INSTALL,
    "q": Command.QUIT,
    "ESC": Command.QUIT,
    "?": Command.HELP,
    "^L": Command.REDRAW,
    "RESIZE": Command.RESIZE,
}


def action_for(symbol: str) -> Command:
    """The command a key symbol triggers on the settings list.

    Unknown keys are ``NONE`` rather than an error: a terminal sending something
    unexpected should do nothing, not end the session.
    """
    return _MAIN.get(symbol, Command.NONE)
