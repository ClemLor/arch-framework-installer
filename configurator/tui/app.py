"""The settings screen and its loop.

Draws what :mod:`configurator.tui.layout` computed, reads a key, and — when the
user edits an entry — hands the real editor from ``build_menu()`` an overlay
backend to ask through. The decision logic stays in the editors; this file owns
nothing but the screen and the keys.
"""

from __future__ import annotations

import curses

from .. import constraints, menu as menu_module, prompts
from ..config import Configuration
from ..menu import Action, Menu
from . import keymap, layout
from .glyphs import glyphs_for
from .screen import CursesPrompts
from .term import Palette, encoding, fill, key_symbol, prepare, safe_addstr

#: Lines reserved below the list: separator, two of help, status, footer.
CHROME_BELOW = 5
#: Lines reserved above: title bar and a blank line.
CHROME_ABOVE = 2

HELP_LINES = 2


class ConfigApp:
    def __init__(
        self,
        window,
        menu: Menu,
        config: Configuration,
        *,
        ascii_only: bool,
        dry_run: bool = False,
    ) -> None:
        self.window = window
        self.menu = menu
        self.config = config
        self.dry_run = dry_run
        self.glyphs = glyphs_for(encoding(), force_ascii=ascii_only)
        self.palette = Palette.create()
        self.selected = 0
        self.top_line = 0
        self.message = ""

    # -- drawing --------------------------------------------------------------

    def draw(self) -> None:
        self.window.erase()
        height, width = self.window.getmaxyx()

        cramped = layout.too_small(width, height)
        if cramped is not None:
            safe_addstr(self.window, 0, 0, cramped, self.palette.blocked)
            safe_addstr(self.window, 1, 0, "q to quit.", self.palette.normal)
            self.window.refresh()
            return

        rows = layout.rows(self.menu, self.config)
        lines = layout.lay_out(rows, width=width, glyphs=self.glyphs)
        room = height - CHROME_ABOVE - CHROME_BELOW
        self.top_line = layout.first_visible(
            lines, selected_row=self.selected, height=room, previous_top=self.top_line
        )

        fill(self.window, 0, self.palette.header)
        safe_addstr(self.window, 0, 1, layout.TITLE, self.palette.header)
        right = self.header_right()
        safe_addstr(
            self.window, 0, max(1, width - len(right) - 1), right, self.palette.header
        )

        for offset, line in enumerate(lines[self.top_line : self.top_line + room]):
            attr = {
                "blocked": self.palette.blocked,
                "note": self.palette.note,
            }.get(line.style, self.palette.normal)
            if line.row == self.selected and line.style == "row":
                attr = self.palette.selected
                # The highlight runs the full width, so it reads as a selected
                # line rather than a differently-coloured word.
                fill(self.window, CHROME_ABOVE + offset, self.palette.selected)
            safe_addstr(self.window, CHROME_ABOVE + offset, 0, line.text, attr)

        separator = height - CHROME_BELOW
        try:
            self.window.hline(separator, 0, curses.ACS_HLINE, width)
        except curses.error:
            pass

        help_text = rows[self.selected].help_text if rows else ""
        for offset, piece in enumerate(layout.wrap(help_text, width - 2)[:HELP_LINES]):
            safe_addstr(
                self.window, separator + 1 + offset, 1, piece, self.palette.help
            )

        status = self.message or "   ".join(
            layout.status_lines(self.menu, self.config)
        )
        attr = self.palette.blocked if constraints.blocking(self.config) else self.palette.normal
        safe_addstr(
            self.window,
            height - 2,
            1,
            layout.truncate(status, width - 2, self.glyphs),
            self.palette.note if self.message else attr,
        )

        fill(self.window, height - 1, self.palette.footer)
        safe_addstr(
            self.window,
            height - 1,
            1,
            layout.truncate(
                layout.footer(dry_run=self.dry_run), width - 2, self.glyphs
            ),
            self.palette.footer,
        )
        self.window.refresh()

    def header_right(self) -> str:
        """Facts the user cannot otherwise see from inside the menu."""
        parts = []
        if self.config.memory_mib:
            parts.append(f"{self.config.memory_mib // 1024} GiB RAM")
        # The keymap is not applied yet while this runs, so free-text fields are
        # typed on whatever layout the console booted with. Saying which one it is
        # costs a corner of the header and saves a puzzling first minute.
        parts.append(f"keymap {self.config.keymap}")
        return "   ".join(parts)

    # -- behaviour ------------------------------------------------------------

    def edit(self) -> None:
        entry = self.menu.entries[self.selected]
        if entry.edit is None:
            self.message = f"{entry.label} is not editable."
            return

        backend = CursesPrompts(self.window, self.palette, self.glyphs)
        backend.context = entry.label
        with prompts.using(backend):
            try:
                note = entry.edit(self.config)
            except prompts.Abandoned:
                self.message = "Left unchanged."
            except ValueError as exc:
                self.message = f"Rejected: {exc}"
            else:
                self.message = note or ""

    def run(self) -> Action:
        while True:
            self.draw()

            code = self.window.getch()
            if code == -1:
                raise EOFError("the terminal went away")
            symbol = key_symbol(code)
            command = keymap.action_for(symbol)
            self.message = ""

            if command is keymap.Command.RESIZE:
                curses.update_lines_cols()
                self.top_line = 0
                continue
            if command is keymap.Command.REDRAW:
                self.window.clearok(True)
                continue
            if command is keymap.Command.QUIT:
                return Action.QUIT
            if command is keymap.Command.SAVE:
                return Action.SAVE
            if command is keymap.Command.INSTALL:
                if self.blockers():
                    self.message = (
                        "Cannot install until the problems above are resolved."
                    )
                    continue
                return Action.INSTALL

            count = len(self.menu.entries)
            if command is keymap.Command.MOVE_DOWN:
                self.selected = (self.selected + 1) % count
            elif command is keymap.Command.MOVE_UP:
                self.selected = (self.selected - 1) % count
            elif command is keymap.Command.PAGE_DOWN:
                self.selected = min(count - 1, self.selected + 5)
            elif command is keymap.Command.PAGE_UP:
                self.selected = max(0, self.selected - 5)
            elif command is keymap.Command.HOME:
                self.selected = 0
            elif command is keymap.Command.END:
                self.selected = count - 1
            elif command is keymap.Command.EDIT:
                self.edit()

    def blockers(self) -> bool:
        return bool(
            constraints.blocking(self.config)
            or menu_module.unanswered(self.menu, self.config)
        )


def main(window, menu: Menu, config: Configuration, dry_run: bool = False) -> Action:
    import os

    prepare(window)
    return ConfigApp(
        window,
        menu,
        config,
        ascii_only=bool(os.environ.get("AFI_TUI_ASCII")),
        dry_run=dry_run,
    ).run()
