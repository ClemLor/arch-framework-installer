"""The questions, separated from what asks them.

The menu entries in :mod:`configurator.menu` decide *what* to ask and hold all
the constraint logic; a backend decides *how*. There is one backend for plain
prompts on standard input and one drawing curses overlays, and the entries do
not know which is installed.

Kept as an indirection rather than a parameter threaded through every editor:
the editors are closures over a single configuration and ask several questions
each, and giving them all a backend argument would change eleven signatures to
carry something none of them make a decision about.
"""

from __future__ import annotations

import contextlib
from collections.abc import Iterator

# (value, description, unavailable/lock reason). A reason present means the
# option is shown but refuses selection, which is the whole point of the menu:
# an option that disappeared teaches the user nothing.
Option = tuple[object, str, str | None]


class Abandoned(Exception):
    """The user left a prompt without answering."""


class Prompts:
    """What every front-end must be able to ask."""

    def text(self, label: str, current: str) -> str:
        raise NotImplementedError

    def boolean(self, label: str, current: bool) -> bool:
        raise NotImplementedError

    def choice(self, label: str, options: list[Option], current: object) -> object:
        raise NotImplementedError

    def checkboxes(
        self,
        label: str,
        options: list[Option],
        selected: list[object],
        *,
        locked_on: list[object] = (),
    ) -> list[object]:
        raise NotImplementedError


class TextPrompts(Prompts):
    """Plain prompts on standard input.

    The fallback when the terminal cannot do better, and what makes the whole
    flow drivable from a script: the questions arrive on standard output and the
    answers are read from standard input, so a recorded session replays.
    """

    def _read(self, prompt: str) -> str:
        answer = input(prompt)
        if answer.strip().lower() in {":q", ":quit"}:
            raise Abandoned
        return answer

    def text(self, label: str, current: str) -> str:
        answer = self._read(f"{label} [{current}]: ").strip()
        return answer or current

    def boolean(self, label: str, current: bool) -> bool:
        default = "Y/n" if current else "y/N"
        while True:
            answer = self._read(f"{label} [{default}]: ").strip().lower()
            if not answer:
                return current
            if answer in {"y", "yes"}:
                return True
            if answer in {"n", "no"}:
                return False
            print("  Answer y or n.")

    def checkboxes(
        self,
        label: str,
        options: list[Option],
        selected: list[object],
        *,
        locked_on: list[object] = (),
    ) -> list[object]:
        """Toggle any number of options, archinstall-style.

        ``locked_on`` values are always selected and cannot be turned off — used
        for the package groups the machine would not boot without, which are
        better shown as permanently ticked than hidden.
        """
        chosen = {
            value for value, _, reason in options if value in selected and not reason
        }
        chosen.update(locked_on)

        print(f"\n{label}")
        while True:
            for number, (value, description, reason) in enumerate(options, start=1):
                if reason:
                    mark = "-"
                elif value in chosen:
                    mark = "x"
                else:
                    mark = " "

                suffix = ""
                if value in locked_on:
                    suffix = "  (always installed)"
                print(f"  {number:>2}) [{mark}] {description}{suffix}")
                if reason:
                    print(f"          unavailable: {reason}")

            print("   a) select all    n) select none    Enter) accept")
            answer = self._read("Toggle: ").strip().lower()

            if not answer:
                return [value for value, _, _ in options if value in chosen]

            if answer == "a":
                chosen = {
                    value for value, _, reason in options if not reason
                } | set(locked_on)
                continue
            if answer == "n":
                chosen = set(locked_on)
                continue

            if not answer.isdigit():
                print("  Enter a number, a, n, or Enter.")
                continue

            index = int(answer) - 1
            if index not in range(len(options)):
                print("  Out of range.")
                continue

            value, description, reason = options[index]
            if reason:
                print(f"  Not available: {reason}")
                continue
            if value in locked_on:
                print(f"  {description} cannot be removed.")
                continue

            chosen.symmetric_difference_update({value})

    def choice(self, label: str, options: list[Option], current: object) -> object:
        """Choose from options, some of which may be locked.

        A locked option is shown and refuses selection with its reason, rather
        than being hidden.
        """
        print(f"\n{label}")
        for number, (value, description, lock) in enumerate(options, start=1):
            mark = "x" if value == current else " "
            if lock:
                print(f"  {number:>2}) [-] {description}")
                print(f"          locked: {lock}")
            else:
                print(f"  {number:>2}) [{mark}] {description}")

        while True:
            answer = self._read("Choose (Enter to keep): ").strip()
            if not answer:
                return current
            if not answer.isdigit():
                print("  Enter a number.")
                continue

            index = int(answer) - 1
            if index not in range(len(options)):
                print("  Out of range.")
                continue

            value, _, lock = options[index]
            if lock:
                print(f"  Not available: {lock}")
                continue
            return value


_active: Prompts = TextPrompts()


def current() -> Prompts:
    """The backend the menu entries will ask through."""
    return _active


@contextlib.contextmanager
def using(backend: Prompts) -> Iterator[Prompts]:
    """Install a backend for the duration of the block.

    Restored in ``finally`` so an exception leaving a curses front-end — or an
    ``Abandoned`` from a test backend — cannot leave the process asking its
    questions through a screen that no longer exists.
    """
    global _active
    previous = _active
    _active = backend
    try:
        yield backend
    finally:
        _active = previous
