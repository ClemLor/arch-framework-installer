"""The live installation screen.

Shown for a dry run only. A real installation still hands the terminal to
``install.sh`` (``__main__.hand_over``): it asks for a passphrase, a typed device
path and two passwords, and a full-screen interface cannot share a terminal with a
child that prompts.

Drawing is a loop over ``runner.poll()`` and ``runner.model``; the layout is
computed by :mod:`configurator.tui.layout`, which is where it can be tested.
"""

from __future__ import annotations

import curses

from ..runner import InstallRunner, Outcome
from . import layout
from .glyphs import glyphs_for
from .term import (
    Palette,
    encoding,
    fill,
    key_symbol,
    prepare,
    raw_keys,
    safe_addstr,
)

#: Lines of chrome: title, blank, then below the list a separator, the log pane,
#: a status line and the footer.
CHROME_ABOVE = 2
LOG_LINES = 8
CHROME_BELOW = LOG_LINES + 3

#: How long a frame waits for something to happen. Short enough that a keypress
#: feels immediate, long enough not to spin a core on an idle installation.
FRAME = 0.08


class InstallScreen:
    def __init__(self, window, runner: InstallRunner, *, ascii_only: bool) -> None:
        self.window = window
        self.runner = runner
        self.glyphs = glyphs_for(encoding(), force_ascii=ascii_only)
        self.palette = Palette.create()
        self.top_line = 0
        self.message = ""
        #: Interrupting a running installation is confirmed, because the first
        #: press might have been aimed at something else and there is a disk
        #: involved.
        self.interrupt_armed = False

    # -- drawing --------------------------------------------------------------

    def draw(self) -> None:
        model = self.runner.model
        self.window.erase()
        height, width = self.window.getmaxyx()

        cramped = layout.too_small(width, height)
        if cramped is not None:
            safe_addstr(self.window, 0, 0, cramped, self.palette.blocked)
            self.window.refresh()
            return

        fill(self.window, 0, self.palette.header)
        safe_addstr(
            self.window, 0, 1, layout.install_header(model), self.palette.header
        )

        lines = layout.install_lines(model, width=width, glyphs=self.glyphs)
        room = max(1, height - CHROME_ABOVE - CHROME_BELOW)
        current = model.current
        focus = model.tasks.index(current) if current is not None else len(lines) - 1
        self.top_line = layout.first_visible(
            lines, selected_row=max(0, focus), height=room, previous_top=self.top_line
        )
        for offset, line in enumerate(lines[self.top_line : self.top_line + room]):
            attr = {
                "selected": self.palette.selected,
                "blocked": self.palette.blocked,
                "note": self.palette.dim,
            }.get(line.style, self.palette.normal)
            safe_addstr(self.window, CHROME_ABOVE + offset, 0, line.text, attr)

        separator = height - CHROME_BELOW
        try:
            self.window.hline(separator, 0, curses.ACS_HLINE, width)
        except curses.error:
            pass

        # The child's own output, which is where the detail lives: pacstrap and
        # sgdisk never go through the installer's logging.
        tail = list(model.output)[-LOG_LINES:]
        for offset, line in enumerate(tail):
            safe_addstr(
                self.window,
                separator + 1 + offset,
                1,
                layout.truncate(line, width - 2, self.glyphs),
                self.palette.dim,
            )

        status = self.message or layout.install_status(model)
        attr = self.palette.normal
        if model.outcome in {Outcome.FAILURE, Outcome.INTERRUPTED}:
            attr = self.palette.blocked
        safe_addstr(
            self.window,
            height - 2,
            1,
            layout.truncate(status, width - 2, self.glyphs),
            attr,
        )

        fill(self.window, height - 1, self.palette.footer)
        safe_addstr(
            self.window, height - 1, 1, layout.install_footer(model), self.palette.footer
        )
        self.window.refresh()

    # -- behaviour ------------------------------------------------------------

    def handle(self, symbol: str) -> bool:
        """Act on a key. Returns False when the screen should close."""
        model = self.runner.model

        if symbol == "RESIZE":
            curses.update_lines_cols()
            self.top_line = 0
            return True

        if model.finished and symbol in {"ENTER", "q", "ESC", " "}:
            return False

        if symbol in {"c", "^C"} and not model.finished:
            if self.interrupt_armed:
                self.interrupt_armed = False
                self.runner.interrupt()
                self.message = (
                    "Interrupt sent. Cleanup and rollback are running; "
                    "press again to escalate."
                )
            else:
                self.interrupt_armed = True
                self.message = "Press c again to interrupt the run."
            return True

        if symbol == "q" and not model.finished:
            # Quitting mid-run would leave a root process installing with nobody
            # watching, so it is not offered as a shortcut for stopping.
            self.message = "Still running. Interrupt with c, or wait."
            return True

        if symbol in {"DOWN", "j"}:
            self.top_line += 1
        elif symbol in {"UP", "k"}:
            self.top_line = max(0, self.top_line - 1)

        return True

    def run(self) -> Outcome:
        # Ctrl-C is wanted as a key, so that interrupting a run goes through the
        # same confirmation as `c` instead of tearing the interface down and
        # leaving the child to be killed on the way out.
        raw_keys(True)
        try:
            while True:
                running = not self.runner.model.finished
                if running:
                    # The frame's wait happens in poll, where it is also useful.
                    self.runner.poll(FRAME)
                # Blocking reads once there is nothing left to watch: with both
                # streams at end-of-file poll returns immediately, and polling a
                # finished run would spin a core while waiting for a keypress.
                self.window.nodelay(running)
                self.draw()

                try:
                    code = self.window.getch()
                except KeyboardInterrupt:
                    # Belt and braces: a terminal that would not go into raw mode
                    # still delivers the signal, and it must mean the same thing.
                    code = 3

                if code != -1:
                    self.message = ""
                    if not self.handle(key_symbol(code)):
                        break
        finally:
            raw_keys(False)
            self.window.nodelay(False)
        return self.runner.model.outcome


def main(window, runner: InstallRunner) -> Outcome:
    import os

    prepare(window)
    return InstallScreen(
        window, runner, ascii_only=bool(os.environ.get("AFI_TUI_ASCII"))
    ).run()
