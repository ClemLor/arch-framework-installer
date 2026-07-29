"""Prompt primitives.

One implementation of each question, used by the plain renderer directly and by
the Textual renderer while suspended. Keeping them here is what stops the two
front-ends from drifting into asking the same thing two different ways.

Every prompt shows the current value and accepts an empty line to keep it, so a
user walking the menu to change one setting never has to retype the rest. Every
prompt can be abandoned, and abandoning leaves the configuration untouched.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import TypeVar

from ..lib.models.size import Size

T = TypeVar("T")


class Abandoned(Exception):
    """The user left a prompt without answering."""


@dataclass(frozen=True)
class Choice:
    """One option in a select prompt."""

    value: object
    label: str
    #: Shown under the label to help the user decide. This is the part that
    #: makes a guided installer guided rather than merely interactive.
    detail: str = ""
    #: Marks an option that cannot be chosen, with the reason as the detail.
    enabled: bool = True


def _read(prompt: str) -> str:
    answer = input(prompt)
    if answer.strip().lower() in {":q", ":quit"}:
        raise Abandoned
    return answer


def ask_text(
    label: str,
    current: str,
    *,
    validate: Callable[[str], str] | None = None,
    help_text: str = "",
) -> str:
    """Free text, defaulting to the current value."""
    if help_text:
        print(help_text)

    while True:
        answer = _read(f"{label} [{current}]: ").strip()
        if not answer:
            return current
        if validate is None:
            return answer
        try:
            return validate(answer)
        except ValueError as exc:
            print(f"  Rejected: {exc}")


def ask_bool(label: str, current: bool, *, help_text: str = "") -> bool:
    if help_text:
        print(help_text)

    default = "Y/n" if current else "y/N"
    while True:
        answer = _read(f"{label} [{default}]: ").strip().lower()
        if not answer:
            return current
        if answer in {"y", "yes"}:
            return True
        if answer in {"n", "no"}:
            return False
        print("  Answer y or n.")


def ask_size(label: str, current: Size, *, help_text: str = "") -> Size:
    def parse(value: str) -> str:
        Size.parse(value)  # raises ValueError with a usable message
        return value

    return Size.parse(ask_text(label, str(current), validate=parse, help_text=help_text))


def _render_choices(choices: Sequence[Choice], selected: set[int]) -> None:
    width = max(len(choice.label) for choice in choices)
    for number, choice in enumerate(choices, start=1):
        mark = "x" if (number - 1) in selected else " "
        disabled = "" if choice.enabled else "  (unavailable)"
        print(f"  {number:>2}) [{mark}] {choice.label.ljust(width)}{disabled}")
        if choice.detail:
            print(f"          {choice.detail}")


def ask_choice(
    label: str,
    choices: Sequence[Choice],
    current: object,
    *,
    help_text: str = "",
) -> object:
    """Pick exactly one option."""
    if not choices:
        raise ValueError(f"{label}: nothing to choose from")
    if help_text:
        print(help_text)

    selectable = [index for index, choice in enumerate(choices) if choice.enabled]
    if not selectable:
        raise ValueError(f"{label}: no option is currently available")

    current_index = next(
        (index for index, choice in enumerate(choices) if choice.value == current),
        None,
    )

    print(f"\n{label}")
    _render_choices(choices, {current_index} if current_index is not None else set())

    while True:
        default = "" if current_index is None else f" [{current_index + 1}]"
        answer = _read(f"Choose{default}: ").strip()

        if not answer:
            if current_index is None:
                print("  Nothing is selected yet; choose a number.")
                continue
            return current

        if not answer.isdigit():
            print("  Enter a number.")
            continue

        index = int(answer) - 1
        if index not in range(len(choices)):
            print("  Out of range.")
            continue
        if not choices[index].enabled:
            print(f"  Unavailable: {choices[index].detail or 'not selectable'}")
            continue
        return choices[index].value


def ask_multi(
    label: str,
    choices: Sequence[Choice],
    current: Sequence[object],
    *,
    minimum: int = 0,
    locked: Sequence[object] = (),
    help_text: str = "",
) -> list[object]:
    """Toggle any number of options.

    ``locked`` values cannot be deselected — used for package groups the machine
    would not boot without.
    """
    if help_text:
        print(help_text)

    selected = {
        index for index, choice in enumerate(choices) if choice.value in current
    }
    locked_indexes = {
        index for index, choice in enumerate(choices) if choice.value in locked
    }
    selected |= locked_indexes

    print(f"\n{label}")
    while True:
        _render_choices(choices, selected)
        if locked_indexes:
            names = ", ".join(choices[index].label for index in sorted(locked_indexes))
            print(f"  Always included: {names}")

        answer = _read("Toggle a number, or Enter to accept: ").strip()
        if not answer:
            if len(selected) < minimum:
                print(f"  Select at least {minimum}.")
                continue
            return [choices[index].value for index in sorted(selected)]

        if not answer.isdigit():
            print("  Enter a number.")
            continue

        index = int(answer) - 1
        if index not in range(len(choices)):
            print("  Out of range.")
            continue
        if index in locked_indexes:
            print(f"  {choices[index].label} cannot be removed.")
            continue
        if not choices[index].enabled:
            print(f"  Unavailable: {choices[index].detail or 'not selectable'}")
            continue

        selected.symmetric_difference_update({index})


def ask_password(label: str, *, confirm: bool = True) -> str:
    """Read a secret without echoing it.

    Falls back to a visible prompt only when there is no terminal to hide it,
    and says so, because silently echoing a passphrase is worse than the
    inconvenience of being told.
    """
    import getpass

    while True:
        try:
            first = getpass.getpass(f"{label}: ")
        except (getpass.GetPassWarning, OSError):
            print("  Warning: input cannot be hidden on this terminal.")
            first = _read(f"{label}: ")

        if not first:
            print("  Empty passphrase rejected.")
            continue
        if not confirm:
            return first

        try:
            again = getpass.getpass(f"{label} (again): ")
        except (getpass.GetPassWarning, OSError):
            again = _read(f"{label} (again): ")

        if first == again:
            return first
        print("  They do not match.")
