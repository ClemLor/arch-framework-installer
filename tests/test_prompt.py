from __future__ import annotations

import pytest

from arch_framework.lib.models import Size
from arch_framework.tui.prompt import (
    Abandoned,
    Choice,
    ask_bool,
    ask_choice,
    ask_multi,
    ask_size,
    ask_text,
)


def answers(monkeypatch, *values: str) -> None:
    stream = iter(values)
    monkeypatch.setattr("builtins.input", lambda *_: next(stream))


# -- text -------------------------------------------------------------------


def test_empty_answer_keeps_the_current_value(monkeypatch) -> None:
    """Walking the menu to change one setting must not mean retyping the rest."""
    answers(monkeypatch, "")
    assert ask_text("Hostname", "framework") == "framework"


def test_text_accepts_a_new_value(monkeypatch) -> None:
    answers(monkeypatch, "laptop")
    assert ask_text("Hostname", "framework") == "laptop"


def test_text_reprompts_after_a_rejected_value(monkeypatch) -> None:
    def validate(value: str) -> str:
        if value == "bad":
            raise ValueError("not allowed")
        return value

    answers(monkeypatch, "bad", "good")
    assert ask_text("Name", "x", validate=validate) == "good"


def test_quit_token_abandons(monkeypatch) -> None:
    answers(monkeypatch, ":q")
    with pytest.raises(Abandoned):
        ask_text("Hostname", "framework")


# -- boolean ----------------------------------------------------------------


@pytest.mark.parametrize(
    ("answer", "current", "expected"),
    [("y", False, True), ("n", True, False), ("", True, True), ("", False, False)],
)
def test_bool(monkeypatch, answer: str, current: bool, expected: bool) -> None:
    answers(monkeypatch, answer)
    assert ask_bool("Enable", current) is expected


def test_bool_reprompts_on_nonsense(monkeypatch) -> None:
    answers(monkeypatch, "maybe", "y")
    assert ask_bool("Enable", False) is True


# -- size -------------------------------------------------------------------


def test_size_accepts_a_valid_value(monkeypatch) -> None:
    answers(monkeypatch, "16GiB")
    assert ask_size("Swap", Size.parse("32GiB")) == Size.parse("16GiB")


def test_size_reprompts_on_a_bad_unit(monkeypatch) -> None:
    answers(monkeypatch, "16GB", "16GiB")
    assert ask_size("Swap", Size.parse("32GiB")) == Size.parse("16GiB")


# -- choice -----------------------------------------------------------------


def test_choice_picks_by_number(monkeypatch) -> None:
    answers(monkeypatch, "2")
    choices = [Choice(value="a", label="A"), Choice(value="b", label="B")]
    assert ask_choice("Pick", choices, "a") == "b"


def test_choice_empty_keeps_current(monkeypatch) -> None:
    answers(monkeypatch, "")
    choices = [Choice(value="a", label="A"), Choice(value="b", label="B")]
    assert ask_choice("Pick", choices, "b") == "b"


def test_choice_refuses_a_disabled_option(monkeypatch) -> None:
    """This is the menu-level half of the disk guard: an ineligible disk is
    shown with its reason but cannot be selected."""
    answers(monkeypatch, "2", "1")
    choices = [
        Choice(value="/dev/nvme0n1", label="/dev/nvme0n1"),
        Choice(
            value="/dev/sdb",
            label="/dev/sdb",
            detail="Rejected: Arch live medium",
            enabled=False,
        ),
    ]
    assert ask_choice("Target", choices, None) == "/dev/nvme0n1"


def test_choice_rejects_out_of_range(monkeypatch) -> None:
    answers(monkeypatch, "9", "1")
    choices = [Choice(value="a", label="A")]
    assert ask_choice("Pick", choices, None) == "a"


def test_choice_with_no_selectable_option_raises() -> None:
    choices = [Choice(value="a", label="A", enabled=False)]
    with pytest.raises(ValueError, match="no option"):
        ask_choice("Pick", choices, None)


def test_choice_with_nothing_to_choose_raises() -> None:
    with pytest.raises(ValueError, match="nothing to choose"):
        ask_choice("Pick", [], None)


# -- multi-select -----------------------------------------------------------


def test_multi_toggles_and_accepts(monkeypatch) -> None:
    answers(monkeypatch, "2", "")
    choices = [Choice(value="a", label="A"), Choice(value="b", label="B")]
    assert ask_multi("Pick", choices, ["a"]) == ["a", "b"]


def test_multi_toggle_is_reversible(monkeypatch) -> None:
    answers(monkeypatch, "1", "1", "")
    choices = [Choice(value="a", label="A")]
    assert ask_multi("Pick", choices, ["a"]) == ["a"]


def test_multi_enforces_a_minimum(monkeypatch) -> None:
    answers(monkeypatch, "1", "", "1", "")
    choices = [Choice(value="a", label="A")]
    assert ask_multi("Pick", choices, ["a"], minimum=1) == ["a"]


def test_multi_refuses_to_drop_a_locked_value(monkeypatch) -> None:
    """Package groups the machine would not boot without cannot be removed."""
    answers(monkeypatch, "1", "")
    choices = [Choice(value="base", label="base"), Choice(value="fonts", label="fonts")]
    assert ask_multi("Groups", choices, ["base"], locked=["base"]) == ["base"]


def test_multi_adds_locked_values_that_were_missing(monkeypatch) -> None:
    answers(monkeypatch, "")
    choices = [Choice(value="base", label="base"), Choice(value="fonts", label="fonts")]
    assert ask_multi("Groups", choices, ["fonts"], locked=["base"]) == ["base", "fonts"]
