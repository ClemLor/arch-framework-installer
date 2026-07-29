"""Tests for the parts of the curses layer that need no terminal.

Skipped whole where ``_curses`` is missing — a Windows interpreter, or a minimal
build — because the point of the front-end split is that everything else in the
suite still runs there.
"""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

if importlib.util.find_spec("_curses") is None:  # pragma: no cover
    raise unittest.SkipTest("no _curses on this interpreter")

import curses  # noqa: E402

from configurator.tui.term import key_symbol  # noqa: E402


class KeySymbolTests(unittest.TestCase):
    def test_the_arrow_keys(self) -> None:
        self.assertEqual(key_symbol(curses.KEY_DOWN), "DOWN")
        self.assertEqual(key_symbol(curses.KEY_UP), "UP")

    def test_both_spellings_of_enter(self) -> None:
        self.assertEqual(key_symbol(10), "ENTER")
        self.assertEqual(key_symbol(13), "ENTER")
        self.assertEqual(key_symbol(curses.KEY_ENTER), "ENTER")

    def test_escape_and_both_backspaces(self) -> None:
        self.assertEqual(key_symbol(27), "ESC")
        self.assertEqual(key_symbol(127), "BACKSPACE")
        self.assertEqual(key_symbol(curses.KEY_BACKSPACE), "BACKSPACE")

    def test_resize_arrives_as_a_key(self) -> None:
        self.assertEqual(key_symbol(curses.KEY_RESIZE), "RESIZE")

    def test_printable_characters_pass_through(self) -> None:
        self.assertEqual(key_symbol(ord("s")), "s")
        self.assertEqual(key_symbol(ord(" ")), " ")

    def test_control_keys_are_named(self) -> None:
        self.assertEqual(key_symbol(12), "^L")
        self.assertEqual(key_symbol(21), "^U")


if __name__ == "__main__":
    unittest.main()
