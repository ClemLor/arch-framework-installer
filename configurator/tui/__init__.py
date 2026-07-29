"""The full-screen front-end.

``curses`` is imported lazily, inside the functions that need it, and never at
module scope anywhere in this package except the three drawing modules. The
configurator has to keep working — including ``--show`` and the whole test suite —
on a Python without ``_curses``, which is every Windows interpreter and any
minimal build.
"""

from __future__ import annotations

import importlib.util
import os
import sys

from ..config import Configuration
from ..menu import Action, Menu


def curses_available() -> bool:
    return importlib.util.find_spec("_curses") is not None


def available() -> bool:
    """Whether a full-screen interface is worth attempting.

    A terminal that cannot address the cursor gets the plain prompts instead of a
    screen full of escape sequences.
    """
    if not curses_available():
        return False
    if os.environ.get("AFI_NO_TUI"):
        return False
    term = os.environ.get("TERM", "")
    if not term or term == "dumb":
        return False
    return bool(sys.stdin.isatty() and sys.stdout.isatty())


def run(menu: Menu, config: Configuration, *, dry_run: bool = False) -> Action:
    """Edit the configuration on a full screen, and return what to do next.

    Deliberately side-effect free apart from ``config``: saving, reporting and
    handing over stay in ``__main__``, and curses is fully torn down before this
    returns so those can print normally — and so a traceback lands on a sane
    terminal.
    """
    import curses
    import locale

    # Before initscr, or every non-ASCII character is drawn as mojibake. A system
    # whose LANG names a locale it has not generated raises here — the live ISO
    # before localisation, or a container — and that is not a reason to refuse to
    # draw: glyphs_for then reports a non-UTF-8 encoding and the ASCII set is used.
    try:
        locale.setlocale(locale.LC_ALL, "")
    except locale.Error:
        pass

    from .app import main

    return curses.wrapper(main, menu, config, dry_run)


def run_installation(runner) -> object:  # runner: configurator.runner.InstallRunner
    """Follow a dry run on a full screen, and return its outcome.

    A separate curses session from ``run``: the configuration screen is torn down
    before this starts, so a traceback from either lands on a restored terminal.
    """
    import curses
    import locale

    try:
        locale.setlocale(locale.LC_ALL, "")
    except locale.Error:
        pass

    from .install import main

    return curses.wrapper(main, runner)
