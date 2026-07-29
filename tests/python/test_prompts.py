"""Tests for the prompt backends.

The menu asks its questions through whichever backend is installed, so these
tests pin two things: the text backend still behaves as it did when its bodies
lived in menu.py, and the delegation actually delegates. If the second one
breaks, a curses front-end silently keeps prompting on standard input.
"""

from __future__ import annotations

import builtins
import contextlib
import io
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from configurator import menu, prompts  # noqa: E402


class Answers:
    """Feeds a scripted sequence to input()."""

    def __init__(self, *values: str) -> None:
        self.values = iter(values)

    def __call__(self, *_: object) -> str:
        return next(self.values)


@contextlib.contextmanager
def scripted(*values: str):
    """Answer input() from a script and swallow what the prompt draws."""
    original = builtins.input
    builtins.input = Answers(*values)
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            yield
    finally:
        builtins.input = original


class Recorder(prompts.Prompts):
    """Records the calls and replays fixed answers."""

    def __init__(self, answer: object = None) -> None:
        self.calls: list[tuple] = []
        self.answer = answer

    def text(self, label: str, current: str) -> str:
        self.calls.append(("text", label, current))
        return str(self.answer)

    def boolean(self, label: str, current: bool) -> bool:
        self.calls.append(("boolean", label, current))
        return bool(self.answer)

    def choice(self, label, options, current):  # type: ignore[no-untyped-def]
        self.calls.append(("choice", label, options, current))
        return self.answer

    def checkboxes(self, label, options, selected, *, locked_on=()):  # type: ignore[no-untyped-def]
        self.calls.append(("checkboxes", label, options, selected, tuple(locked_on)))
        return list(self.answer or [])


class TextBackendTests(unittest.TestCase):
    def setUp(self) -> None:
        self.backend = prompts.TextPrompts()

    def test_empty_answer_keeps_the_current_value(self) -> None:
        """The one behaviour every front-end has to reproduce: an untouched
        field is not an instruction to blank the setting."""
        with scripted(""):
            self.assertEqual(self.backend.text("Hostname", "framework"), "framework")

    def test_whitespace_only_answer_keeps_the_current_value(self) -> None:
        with scripted("   "):
            self.assertEqual(self.backend.text("Hostname", "framework"), "framework")

    def test_quit_abandons_the_prompt(self) -> None:
        with scripted(":q"):
            with self.assertRaises(prompts.Abandoned):
                self.backend.text("Hostname", "framework")

    def test_boolean_rejects_nonsense_and_asks_again(self) -> None:
        with scripted("maybe", "y"):
            self.assertTrue(self.backend.boolean("Encrypt", False))

    def test_choice_keeps_the_current_value_on_enter(self) -> None:
        options = [("a", "first", None), ("b", "second", None)]
        with scripted(""):
            self.assertEqual(self.backend.choice("Pick", options, "b"), "b")

    def test_choice_refuses_a_locked_option(self) -> None:
        options = [("a", "first", "not on this disk"), ("b", "second", None)]
        with scripted("1", "2"):
            self.assertEqual(self.backend.choice("Pick", options, None), "b")

    def test_checkboxes_return_display_order(self) -> None:
        options = [("a", "first", None), ("b", "second", None), ("c", "third", None)]
        with scripted("3", "1", ""):
            self.assertEqual(
                self.backend.checkboxes("Pick", options, ["b"]), ["a", "b", "c"]
            )

    def test_checkboxes_cannot_untick_a_locked_group(self) -> None:
        options = [("base", "base", None), ("extra", "extra", None)]
        with scripted("1", "n", ""):
            self.assertEqual(
                self.backend.checkboxes(
                    "Groups", options, ["base", "extra"], locked_on=["base"]
                ),
                ["base"],
            )


class DelegationTests(unittest.TestCase):
    def test_the_four_helpers_go_through_the_active_backend(self) -> None:
        recorder = Recorder(answer="answered")
        with prompts.using(recorder):
            menu.ask_text("Hostname", "framework")
            menu.ask_bool("Encrypt", True)
            menu.ask_locked_choice("Pick", [("a", "first", None)], "a")
            menu.ask_checkboxes(
                "Groups", [("base", "base", None)], ["base"], locked_on=["base"]
            )

        kinds = [call[0] for call in recorder.calls]
        self.assertEqual(kinds, ["text", "boolean", "choice", "checkboxes"])
        self.assertEqual(recorder.calls[3][4], ("base",))

    def test_the_default_backend_is_the_text_one(self) -> None:
        self.assertIsInstance(prompts.current(), prompts.TextPrompts)

    def test_using_restores_the_previous_backend(self) -> None:
        before = prompts.current()
        with prompts.using(Recorder()):
            self.assertNotEqual(prompts.current(), before)
        self.assertIs(prompts.current(), before)

    def test_using_restores_even_when_the_block_raises(self) -> None:
        """A front-end that dies must not leave the process asking its questions
        through a screen that no longer exists."""
        before = prompts.current()
        with self.assertRaises(RuntimeError):
            with prompts.using(Recorder()):
                raise RuntimeError("front-end died")
        self.assertIs(prompts.current(), before)

    def test_the_menu_abandon_exception_is_the_shared_one(self) -> None:
        """run() catches menu._Abandoned; a backend raising prompts.Abandoned has
        to be the same class or every cancellation becomes a traceback."""
        self.assertIs(menu._Abandoned, prompts.Abandoned)


if __name__ == "__main__":
    unittest.main()
