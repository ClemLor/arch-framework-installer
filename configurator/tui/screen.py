"""The four questions, as curses overlays.

The editors in :mod:`configurator.menu` ask through
:class:`configurator.prompts.Prompts`, so this module only has to draw and read
keys. What it must not do is diverge in behaviour from the text backend: an empty
text field keeps the current value, a locked option refuses selection with its
reason, mandatory checkboxes cannot be unticked, and the returned order of a
multi-selection is the display order. Each of those is pinned by a test.
"""

from __future__ import annotations

import curses

from .. import prompts
from . import layout
from .glyphs import Glyphs
from .term import Palette, fill, key_symbol, safe_addstr, show_cursor

#: Rows of chrome an overlay spends on its title, blank lines and footer.
CHROME = 5


class CursesPrompts(prompts.Prompts):
    """Draws the prompts on a centred panel over the settings list."""

    def __init__(self, window, palette: Palette, glyphs: Glyphs) -> None:
        self.window = window
        self.palette = palette
        self.glyphs = glyphs
        #: The entry currently being edited, shown as a breadcrumb. Several
        #: questions can belong to one entry, and without it the third overlay of
        #: "Memory and hibernation" looks like it came from nowhere.
        self.context = ""

    # -- drawing --------------------------------------------------------------

    def _title(self, label: str) -> str:
        if self.context and self.context != label:
            return f"{self.context} — {label}"
        return label

    def _geometry(self) -> tuple[int, int, int, int]:
        """Where the panel goes: (top, left, height, width)."""
        height, width = self.window.getmaxyx()
        panel_width = min(max(width - 8, 20), max(width, 20))
        panel_width = min(panel_width, width)
        panel_height = min(max(height - 4, 6), height)
        top = max(0, (height - panel_height) // 2)
        left = max(0, (width - panel_width) // 2)
        return top, left, panel_height, panel_width

    def _draw(
        self, label: str, lines: list[layout.Line], top_line: int, footer: str, status: str
    ) -> int:
        """Paint a panel and return how many item lines fitted."""
        self.window.erase()
        top, left, height, width = self._geometry()

        fill(self.window, top, self.palette.header)
        safe_addstr(
            self.window,
            top,
            left + 1,
            layout.truncate(self._title(label), width - 2, self.glyphs),
            self.palette.header,
        )

        room = max(1, height - CHROME)
        for offset, line in enumerate(lines[top_line : top_line + room]):
            attr = {
                "selected": self.palette.selected,
                "blocked": self.palette.blocked,
                "note": self.palette.note,
                "locked": self.palette.locked,
            }.get(line.style, self.palette.normal)
            safe_addstr(
                self.window,
                top + 2 + offset,
                left + 1,
                layout.truncate(line.text, width - 2, self.glyphs),
                attr,
            )

        if status:
            for offset, piece in enumerate(layout.wrap(status, width - 2)[:1]):
                safe_addstr(
                    self.window,
                    top + height - 2,
                    left + 1,
                    piece,
                    self.palette.blocked,
                )

        fill(self.window, top + height - 1, self.palette.footer)
        safe_addstr(
            self.window,
            top + height - 1,
            left + 1,
            layout.truncate(footer, width - 2, self.glyphs),
            self.palette.footer,
        )
        self.window.refresh()
        return room

    def _read_key(self) -> str:
        code = self.window.getch()
        if code == -1:
            raise EOFError("the terminal went away")
        return key_symbol(code)

    # -- option lists ---------------------------------------------------------

    def _option_lines(
        self,
        options: list[prompts.Option],
        *,
        marks: dict[int, str],
        selected_index: int,
        suffixes: dict[int, str],
        reason_word: str,
    ) -> list[layout.Line]:
        _, _, _, width = self._geometry()
        room = max(10, width - 6)

        lines: list[layout.Line] = []
        for index, (_, description, reason) in enumerate(options):
            style = "selected" if index == selected_index else (
                "locked" if reason else "row"
            )
            text = f" {marks[index]} {description}{suffixes.get(index, '')}"
            lines.append(layout.Line(text, style, index))
            if reason:
                for piece in layout.wrap(f"{reason_word}: {reason}", room - 6):
                    lines.append(layout.Line("      " + piece, "note", index))
        return lines

    def _navigate(
        self, symbol: str, index: int, count: int, room: int
    ) -> int | None:
        if symbol in {"DOWN", "j"}:
            return (index + 1) % count
        if symbol in {"UP", "k"}:
            return (index - 1) % count
        if symbol == "NPAGE":
            return min(count - 1, index + max(1, room - 1))
        if symbol == "PPAGE":
            return max(0, index - max(1, room - 1))
        if symbol == "HOME":
            return 0
        if symbol == "END":
            return count - 1
        return None

    def choice(self, label: str, options: list[prompts.Option], current: object) -> object:
        if not options:
            raise ValueError("nothing to choose")

        index = next(
            (i for i, (value, _, lock) in enumerate(options) if value == current), 0
        )
        top_line = 0
        status = ""
        room = 1

        while True:
            marks = {
                i: (
                    self.glyphs.check_locked
                    if lock
                    else self.glyphs.radio_on
                    if value == current
                    else self.glyphs.radio_off
                )
                for i, (value, _, lock) in enumerate(options)
            }
            lines = self._option_lines(
                options,
                marks=marks,
                selected_index=index,
                suffixes={},
                reason_word="locked",
            )
            room = self._draw(
                label,
                lines,
                top_line,
                "^v move   Enter select   Esc cancel",
                status,
            )
            top_line = layout.first_visible(
                lines, selected_row=index, height=room, previous_top=top_line
            )

            symbol = self._read_key()
            status = ""
            if symbol == "RESIZE":
                curses.update_lines_cols()
                top_line = 0
                continue
            if symbol == "ESC":
                raise prompts.Abandoned

            moved = self._navigate(symbol, index, len(options), room)
            if moved is not None:
                index = moved
                continue

            if symbol in {"ENTER", " "}:
                value, _, lock = options[index]
                if lock:
                    status = f"Not available: {lock}"
                    continue
                return value

    def boolean(self, label: str, current: bool) -> bool:
        options: list[prompts.Option] = [(True, "yes", None), (False, "no", None)]
        index = 0 if current else 1
        top_line = 0

        while True:
            marks = {
                i: (
                    self.glyphs.radio_on
                    if value == current
                    else self.glyphs.radio_off
                )
                for i, (value, _, _) in enumerate(options)
            }
            lines = self._option_lines(
                options,
                marks=marks,
                selected_index=index,
                suffixes={},
                reason_word="locked",
            )
            room = self._draw(
                label, lines, top_line, "^v move   y/n   Enter select   Esc cancel", ""
            )
            top_line = layout.first_visible(
                lines, selected_row=index, height=room, previous_top=top_line
            )

            symbol = self._read_key()
            if symbol == "RESIZE":
                curses.update_lines_cols()
                continue
            if symbol == "ESC":
                raise prompts.Abandoned
            if symbol in {"y", "Y"}:
                return True
            if symbol in {"n", "N"}:
                return False

            moved = self._navigate(symbol, index, len(options), room)
            if moved is not None:
                index = moved
                continue
            if symbol in {"ENTER", " "}:
                return bool(options[index][0])

    def checkboxes(
        self,
        label: str,
        options: list[prompts.Option],
        selected: list[object],
        *,
        locked_on: list[object] = (),
    ) -> list[object]:
        # Same seeding as the text backend: an unavailable option is never
        # selected on the user's behalf, and the mandatory ones always are.
        chosen = {
            value for value, _, reason in options if value in selected and not reason
        }
        chosen.update(locked_on)

        index = 0
        top_line = 0
        status = ""

        while True:
            marks = {}
            suffixes = {}
            for i, (value, _, reason) in enumerate(options):
                if reason:
                    marks[i] = self.glyphs.check_locked
                elif value in chosen:
                    marks[i] = self.glyphs.check_on
                else:
                    marks[i] = self.glyphs.check_off
                if value in locked_on:
                    suffixes[i] = "  (always installed)"

            lines = self._option_lines(
                options,
                marks=marks,
                selected_index=index,
                suffixes=suffixes,
                reason_word="unavailable",
            )
            room = self._draw(
                label,
                lines,
                top_line,
                "Space toggle   a all   n none   Enter accept   Esc cancel",
                status,
            )
            top_line = layout.first_visible(
                lines, selected_row=index, height=room, previous_top=top_line
            )

            symbol = self._read_key()
            status = ""
            if symbol == "RESIZE":
                curses.update_lines_cols()
                top_line = 0
                continue
            if symbol == "ESC":
                raise prompts.Abandoned

            moved = self._navigate(symbol, index, len(options), room)
            if moved is not None:
                index = moved
                continue

            if symbol == "a":
                chosen = {
                    value for value, _, reason in options if not reason
                } | set(locked_on)
                continue
            if symbol == "n":
                chosen = set(locked_on)
                continue
            if symbol == "ENTER":
                return [value for value, _, _ in options if value in chosen]
            if symbol == " ":
                value, description, reason = options[index]
                if reason:
                    status = f"Not available: {reason}"
                    continue
                if value in locked_on:
                    status = f"{description} cannot be removed."
                    continue
                chosen.symmetric_difference_update({value})

    # -- text -----------------------------------------------------------------

    def text(self, label: str, current: str) -> str:
        editor = layout.LineEditor(current)
        show_cursor(True)
        try:
            while True:
                top, left, height, width = self._geometry()
                field_width = max(4, width - 6)
                visible, column = editor.window(field_width)

                self.window.erase()
                fill(self.window, top, self.palette.header)
                safe_addstr(
                    self.window,
                    top,
                    left + 1,
                    layout.truncate(self._title(label), width - 2, self.glyphs),
                    self.palette.header,
                )
                safe_addstr(
                    self.window,
                    top + 2,
                    left + 2,
                    visible.ljust(field_width),
                    self.palette.selected,
                )
                safe_addstr(
                    self.window,
                    top + 4,
                    left + 2,
                    layout.truncate(
                        f"current: {current}" if current else "currently unset",
                        width - 4,
                        self.glyphs,
                    ),
                    self.palette.help,
                )
                fill(self.window, top + height - 1, self.palette.footer)
                safe_addstr(
                    self.window,
                    top + height - 1,
                    left + 1,
                    "Enter accept (empty keeps the current value)   Esc cancel",
                    self.palette.footer,
                )
                try:
                    self.window.move(top + 2, left + 2 + column)
                except curses.error:
                    pass
                self.window.refresh()

                symbol = self._read_key()
                if symbol == "RESIZE":
                    curses.update_lines_cols()
                    continue
                if symbol == "ESC":
                    raise prompts.Abandoned
                if symbol == "ENTER":
                    # Identical rule to the text backend: nothing typed means the
                    # setting is left as it was, not blanked.
                    return editor.buffer.strip() or current
                editor.apply(symbol)
        finally:
            show_cursor(False)
