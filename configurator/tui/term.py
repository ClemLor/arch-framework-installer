"""The thin layer that actually touches curses.

Everything here is about the terminal rather than the installer: turning key codes
into symbols, writing text without falling over the bottom-right cell, and picking
attributes that still mean something on a console with no colour.
"""

from __future__ import annotations

import curses
from dataclasses import dataclass

#: Curses key constants to the symbols keymap.py speaks.
_KEYS: dict[int, str] = {
    curses.KEY_UP: "UP",
    curses.KEY_DOWN: "DOWN",
    curses.KEY_LEFT: "LEFT",
    curses.KEY_RIGHT: "RIGHT",
    curses.KEY_HOME: "HOME",
    curses.KEY_END: "END",
    curses.KEY_PPAGE: "PPAGE",
    curses.KEY_NPAGE: "NPAGE",
    curses.KEY_DC: "DC",
    curses.KEY_BACKSPACE: "BACKSPACE",
    curses.KEY_ENTER: "ENTER",
    curses.KEY_RESIZE: "RESIZE",
    10: "ENTER",
    13: "ENTER",
    27: "ESC",
    8: "BACKSPACE",
    127: "BACKSPACE",
    12: "^L",
    21: "^U",
    3: "^C",
}


def key_symbol(code: int) -> str:
    """A key code as a symbol. ``""`` for a code with no useful meaning."""
    if code in _KEYS:
        return _KEYS[code]
    if 32 <= code < 127:
        return chr(code)
    if 0 <= code < 32:
        return f"^{chr(code + 64)}"
    try:
        return chr(code)
    except ValueError:
        return ""


def safe_addstr(window, y: int, x: int, text: str, attr: int = 0) -> None:
    """Write text, clipped to the window.

    Writing to the last cell of the last line always raises, and a terminal that
    shrank between the layout and the draw would raise too. Neither is a reason to
    end the session with a traceback.
    """
    height, width = window.getmaxyx()
    if y < 0 or y >= height or x >= width:
        return
    room = width - x
    if room <= 0:
        return
    clipped = text[:room]
    if y == height - 1 and len(clipped) == room:
        clipped = clipped[:-1]
    if not clipped:
        return
    try:
        window.addstr(y, x, clipped, attr)
    except curses.error:
        pass


def fill(window, y: int, attr: int) -> None:
    """Paint a whole line with an attribute, for header and footer bars."""
    height, width = window.getmaxyx()
    if 0 <= y < height:
        safe_addstr(window, y, 0, " " * width, attr)


@dataclass
class Palette:
    """Attributes by role.

    Colour is an enhancement, never the carrier: the same information is legible
    through reverse video, bold and dim, because the Linux console can be
    configured with no colour at all and because a colour-blind reader must not
    be the only one who cannot see which line is blocked.
    """

    normal: int
    selected: int
    blocked: int
    note: int
    help: int
    header: int
    footer: int
    locked: int
    dim: int

    @classmethod
    def create(cls) -> "Palette":
        if not curses.has_colors():
            return cls(
                normal=curses.A_NORMAL,
                selected=curses.A_REVERSE,
                blocked=curses.A_BOLD,
                note=curses.A_DIM,
                help=curses.A_DIM,
                header=curses.A_REVERSE,
                footer=curses.A_REVERSE,
                locked=curses.A_DIM,
                dim=curses.A_DIM,
            )

        try:
            curses.use_default_colors()
            background = -1
        except curses.error:
            background = curses.COLOR_BLACK

        curses.init_pair(1, curses.COLOR_RED, background)
        curses.init_pair(2, curses.COLOR_YELLOW, background)
        curses.init_pair(3, curses.COLOR_CYAN, background)
        curses.init_pair(4, curses.COLOR_GREEN, background)

        return cls(
            normal=curses.A_NORMAL,
            selected=curses.A_REVERSE,
            blocked=curses.color_pair(1) | curses.A_BOLD,
            note=curses.color_pair(2),
            help=curses.color_pair(3),
            header=curses.A_REVERSE | curses.A_BOLD,
            footer=curses.A_REVERSE,
            locked=curses.A_DIM,
            dim=curses.A_DIM,
        )


def prepare(window) -> None:
    """Put the terminal into the state the interface assumes."""
    try:
        curses.curs_set(0)
    except curses.error:
        # Some terminals cannot hide the cursor; not a reason to refuse to run.
        pass
    window.keypad(True)
    window.nodelay(False)
    if hasattr(curses, "set_escdelay"):
        # Without this, escape — the universal cancel key here — takes a second.
        curses.set_escdelay(25)


def raw_keys(enabled: bool) -> None:
    """Whether Ctrl-C arrives as a key or as a signal.

    The installation screen wants the key: interrupting a run is a decision with a
    confirmation attached, not something a stray keypress does. ``curses.wrapper``
    leaves ISIG on, so this has to be asked for explicitly — and turned back off,
    or the terminal is left unable to interrupt anything.
    """
    try:
        curses.raw() if enabled else curses.cbreak()
    except curses.error:
        pass


def show_cursor(visible: bool) -> None:
    try:
        curses.curs_set(1 if visible else 0)
    except curses.error:
        pass


def encoding() -> str:
    """What the terminal claims it can render."""
    import locale

    return locale.getpreferredencoding(False)
