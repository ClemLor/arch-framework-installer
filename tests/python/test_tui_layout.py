"""Tests for the full-screen layout, with no terminal involved.

Everything the interface decides — what a row reads, where a violation goes,
what stays visible when the list scrolls, how a text field behaves — is computed
by pure functions, so it is checked here rather than by looking at a screen. The
curses modules that consume this are a thin drawing layer on top.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from configurator.config import Configuration, Size  # noqa: E402
from configurator.menu import NOT_SET, build_menu  # noqa: E402
from configurator.tui import glyphs as glyph_module  # noqa: E402
from configurator.tui import keymap, layout  # noqa: E402

GIB = 1024
ASCII = glyph_module.ASCII


def blocked_config() -> Configuration:
    """Hibernation on with a swapfile too small to hold memory."""
    return Configuration(
        memory_mib=32 * GIB,
        hibernation_enabled=True,
        swap_size=Size(8 * GIB),
        btrfs_subvolumes=["@", "@home", "@swap"],
    )


class RowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.menu = build_menu()

    def test_mandatory_entries_are_marked_and_unset_values_say_so(self) -> None:
        rows = layout.rows(self.menu, Configuration())
        disk = next(row for row in rows if row.key == "target_disk")

        self.assertTrue(disk.mandatory)
        self.assertEqual(disk.value, NOT_SET)

    def test_a_blocking_violation_is_tagged_differently_from_advice(self) -> None:
        rows = {row.key: row for row in layout.rows(self.menu, blocked_config())}

        self.assertTrue(rows["swap_size"].blocking)
        self.assertTrue(rows["swap_size"].annotation.startswith("BLOCKED: "))
        # TPM2 is on by default and carries the recovery advisory, not a block.
        self.assertFalse(rows["tpm2_enabled"].blocking)
        self.assertTrue(rows["tpm2_enabled"].annotation.startswith("note: "))

    def test_a_setting_with_no_problem_has_no_annotation(self) -> None:
        rows = {row.key: row for row in layout.rows(self.menu, Configuration())}
        self.assertIsNone(rows["locale"].annotation)


class RowFormattingTests(unittest.TestCase):
    def row(self, **overrides: object) -> layout.Row:
        base = dict(
            key="target_disk",
            label="Target disk",
            value="/dev/nvme0n1",
            mandatory=True,
            annotation=None,
            blocking=False,
            editable=True,
            help_text="",
        )
        base.update(overrides)
        return layout.Row(**base)  # type: ignore[arg-type]

    def test_the_label_is_filled_out_to_the_value(self) -> None:
        line = layout.format_row(
            self.row(), width=60, glyphs=ASCII, label_width=len("Memory and hibernation")
        )
        self.assertTrue(line.startswith("* Target disk ....."))
        self.assertTrue(line.endswith("/dev/nvme0n1"))

    def test_an_optional_entry_has_no_marker(self) -> None:
        line = layout.format_row(
            self.row(mandatory=False), width=60, glyphs=ASCII, label_width=11
        )
        self.assertTrue(line.startswith("  Target disk"))

    def test_a_narrow_terminal_truncates_rather_than_wrapping(self) -> None:
        for width in (40, 20, 8, 3, 1):
            line = layout.format_row(
                self.row(), width=width, glyphs=ASCII, label_width=11
            )
            self.assertLessEqual(len(line), width, width)

    def test_truncation_is_visible(self) -> None:
        line = layout.format_row(self.row(), width=20, glyphs=ASCII, label_width=11)
        self.assertTrue(line.endswith(ASCII.ellipsis))


class LayoutTests(unittest.TestCase):
    def setUp(self) -> None:
        self.rows = layout.rows(build_menu(), blocked_config())
        self.lines = layout.lay_out(self.rows, width=80, glyphs=ASCII)

    def test_every_row_produces_at_least_one_line(self) -> None:
        owners = {line.row for line in self.lines}
        self.assertEqual(owners, set(range(len(self.rows))))

    def test_an_annotation_line_belongs_to_its_setting(self) -> None:
        index = next(i for i, row in enumerate(self.rows) if row.key == "swap_size")
        owned = [line for line in self.lines if line.row == index]

        self.assertGreater(len(owned), 1)
        self.assertEqual(owned[0].style, "row")
        self.assertTrue(all(line.style == "blocked" for line in owned[1:]))

    def test_no_line_exceeds_the_width(self) -> None:
        lines = layout.lay_out(self.rows, width=48, glyphs=ASCII)
        self.assertTrue(all(len(line.text) <= 48 for line in lines))


class ScrollingTests(unittest.TestCase):
    def lines(self) -> list[layout.Line]:
        return layout.lay_out(
            layout.rows(build_menu(), blocked_config()), width=80, glyphs=ASCII
        )

    def test_the_first_row_needs_no_scrolling(self) -> None:
        self.assertEqual(
            layout.first_visible(self.lines(), selected_row=0, height=8), 0
        )

    def test_the_last_row_is_brought_into_view(self) -> None:
        lines = self.lines()
        last = max(line.row for line in lines if line.row is not None)
        top = layout.first_visible(lines, selected_row=last, height=6)

        visible = lines[top : top + 6]
        self.assertIn(last, [line.row for line in visible])

    def test_a_reason_is_not_scrolled_off_its_setting(self) -> None:
        """A BLOCKED line with its label out of view, or a label whose reason is
        just below the fold, is exactly the confusion the annotation exists to
        prevent."""
        lines = self.lines()
        rows = layout.rows(build_menu(), blocked_config())
        index = next(i for i, row in enumerate(rows) if row.key == "swap_size")

        top = layout.first_visible(lines, selected_row=index, height=5)
        visible = [line for line in lines[top : top + 5] if line.row == index]
        owned = [line for line in lines if line.row == index]
        self.assertEqual(len(visible), len(owned))

    def test_a_selection_already_on_screen_does_not_move_the_view(self) -> None:
        """Moving the selection must not make the list jump under the user."""
        lines = [layout.Line(f"row {i}", "row", i) for i in range(20)]
        self.assertEqual(
            layout.first_visible(lines, selected_row=3, height=5, previous_top=1), 1
        )

    def test_a_list_that_fits_is_never_scrolled(self) -> None:
        lines = [layout.Line(f"row {i}", "row", i) for i in range(4)]
        self.assertEqual(
            layout.first_visible(lines, selected_row=3, height=20, previous_top=1), 0
        )

    def test_no_rows_and_no_height_are_survivable(self) -> None:
        self.assertEqual(layout.first_visible([], selected_row=0, height=10), 0)
        self.assertEqual(layout.first_visible(self.lines(), selected_row=0, height=0), 0)


class WrapTests(unittest.TestCase):
    def test_wrapping_never_exceeds_the_width(self) -> None:
        text = "Hibernation writes the contents of memory to persistent storage."
        for width in (1, 2, 7, 30, 200):
            self.assertTrue(
                all(len(piece) <= width for piece in layout.wrap(text, width)), width
            )

    def test_an_unbreakable_token_is_broken_rather_than_dropped(self) -> None:
        pieces = layout.wrap("x" * 200, 30)
        self.assertEqual("".join(pieces), "x" * 200)

    def test_a_nonsense_width_yields_nothing_instead_of_raising(self) -> None:
        self.assertEqual(layout.wrap("anything", 0), [])


class ChromeTests(unittest.TestCase):
    def test_the_status_names_what_is_missing(self) -> None:
        menu = build_menu()
        lines = layout.status_lines(menu, blocked_config())
        joined = " ".join(lines)

        self.assertIn("blocking problem", joined)
        self.assertIn("Target disk", joined)

    def test_a_clean_configuration_says_so(self) -> None:
        menu = build_menu()
        config = Configuration(target_disk="/dev/nvme0n1", disk_size_mib=900 * GIB)
        config.answered.update({"target_disk", "username"})

        self.assertEqual(layout.status_lines(menu, config), ["Ready to install."])

    def test_the_footer_names_every_key(self) -> None:
        text = layout.footer()
        for key in ("Enter", "s ", "i ", "q "):
            self.assertIn(key, text)

    def test_the_install_key_says_which_of_the_two_it_is(self) -> None:
        """A dry run keeps the screen; a real installation hands the terminal to
        install.sh. Finding out afterwards reads as a bug."""
        self.assertIn("dry run", layout.footer(dry_run=True))
        self.assertIn("real", layout.footer(dry_run=False))

    def test_too_small_reports_both_sizes(self) -> None:
        self.assertIsNone(layout.too_small(80, 24))
        message = layout.too_small(40, 10)
        self.assertIn("40x10", message)
        self.assertIn(f"{layout.MIN_WIDTH}x{layout.MIN_HEIGHT}", message)


class GlyphTests(unittest.TestCase):
    def test_a_utf8_console_gets_the_unicode_set(self) -> None:
        self.assertIs(glyph_module.glyphs_for("UTF-8"), glyph_module.UNICODE)
        self.assertIs(glyph_module.glyphs_for("utf8"), glyph_module.UNICODE)

    def test_anything_else_gets_ascii(self) -> None:
        self.assertIs(glyph_module.glyphs_for("ANSI_X3.4-1968"), glyph_module.ASCII)
        self.assertIs(glyph_module.glyphs_for(None), glyph_module.ASCII)

    def test_ascii_can_be_forced_on_a_lying_console(self) -> None:
        self.assertIs(
            glyph_module.glyphs_for("UTF-8", force_ascii=True), glyph_module.ASCII
        )


class KeymapTests(unittest.TestCase):
    def test_movement(self) -> None:
        self.assertEqual(keymap.action_for("DOWN"), keymap.Command.MOVE_DOWN)
        self.assertEqual(keymap.action_for("j"), keymap.Command.MOVE_DOWN)
        self.assertEqual(keymap.action_for("UP"), keymap.Command.MOVE_UP)

    def test_the_three_decisions(self) -> None:
        self.assertEqual(keymap.action_for("s"), keymap.Command.SAVE)
        self.assertEqual(keymap.action_for("i"), keymap.Command.INSTALL)
        self.assertEqual(keymap.action_for("q"), keymap.Command.QUIT)
        self.assertEqual(keymap.action_for("ESC"), keymap.Command.QUIT)

    def test_edit(self) -> None:
        self.assertEqual(keymap.action_for("ENTER"), keymap.Command.EDIT)
        self.assertEqual(keymap.action_for(" "), keymap.Command.EDIT)

    def test_an_unknown_key_does_nothing(self) -> None:
        self.assertEqual(keymap.action_for("F13"), keymap.Command.NONE)


class LineEditorTests(unittest.TestCase):
    def test_it_starts_at_the_end_of_the_current_value(self) -> None:
        editor = layout.LineEditor("framework")
        editor.apply("2")
        self.assertEqual(editor.buffer, "framework2")

    def test_backspace_at_the_start_does_nothing(self) -> None:
        editor = layout.LineEditor("abc")
        editor.apply("HOME")
        editor.apply("BACKSPACE")
        self.assertEqual(editor.buffer, "abc")
        self.assertEqual(editor.cursor, 0)

    def test_insert_at_the_cursor(self) -> None:
        editor = layout.LineEditor("abc")
        editor.apply("HOME")
        editor.apply("RIGHT")
        editor.apply("X")
        self.assertEqual(editor.buffer, "aXbc")

    def test_delete_forward(self) -> None:
        editor = layout.LineEditor("abc")
        editor.apply("HOME")
        editor.apply("DC")
        self.assertEqual(editor.buffer, "bc")

    def test_clear(self) -> None:
        editor = layout.LineEditor("abc")
        editor.apply("^U")
        self.assertEqual((editor.buffer, editor.cursor), ("", 0))

    def test_a_long_value_scrolls_and_keeps_the_cursor_visible(self) -> None:
        """With the cursor past the last character, the window shows the tail and
        leaves the final column for the cursor itself."""
        editor = layout.LineEditor("/usr/bin/fish-with-a-very-long-path")
        text, column = editor.window(10)

        self.assertEqual(len(text), 9)
        self.assertEqual(column, 9)
        self.assertTrue(editor.buffer.endswith(text))

    def test_moving_back_scrolls_the_window_back(self) -> None:
        editor = layout.LineEditor("0123456789abcdef")
        editor.window(6)
        editor.apply("HOME")
        text, column = editor.window(6)

        self.assertEqual(text, "012345")
        self.assertEqual(column, 0)


if __name__ == "__main__":
    unittest.main()
