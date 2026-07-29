from __future__ import annotations

from arch_framework.tui.menu import NOT_SET, Action, MenuEntry, MenuRegistry
from arch_framework.tui.plain import PlainRenderer


def build_registry() -> MenuRegistry:
    return (
        MenuRegistry()
        .add(
            MenuEntry(
                key="hostname",
                label="Hostname",
                preview=lambda config: config["hostname"],
                edit=lambda config: config.update(hostname="edited"),
            )
        )
        .add(
            MenuEntry(
                key="disk",
                label="Disk configuration",
                preview=lambda config: config["disk"] or NOT_SET,
                mandatory=True,
            )
        )
    )


def test_render_shows_values_and_marks_mandatory() -> None:
    lines = build_registry().render_lines({"hostname": "framework", "disk": ""})
    assert "framework" in lines[0]
    assert "*" in lines[1]
    assert NOT_SET in lines[1]


def test_unanswered_mandatory_detected() -> None:
    registry = build_registry()
    config = {"hostname": "framework", "disk": ""}
    assert [entry.key for entry in registry.unanswered_mandatory(config)] == ["disk"]
    config["disk"] = "/dev/nvme0n1"
    assert registry.unanswered_mandatory(config) == []


def test_install_blocked_while_mandatory_unanswered(monkeypatch) -> None:
    """The guard is what stops a half-answered menu from partitioning a disk."""
    registry = build_registry()
    config = {"hostname": "framework", "disk": ""}
    answers = iter(["i", "q"])
    monkeypatch.setattr("builtins.input", lambda *_: next(answers))

    assert PlainRenderer(registry).run(config) is Action.ABORT


def test_install_allowed_once_answered(monkeypatch) -> None:
    registry = build_registry()
    config = {"hostname": "framework", "disk": "/dev/nvme0n1"}
    monkeypatch.setattr("builtins.input", lambda *_: "i")

    assert PlainRenderer(registry).run(config) is Action.INSTALL


def test_numeric_choice_edits_the_entry(monkeypatch) -> None:
    registry = build_registry()
    config = {"hostname": "framework", "disk": "/dev/nvme0n1"}
    answers = iter(["1", "s"])
    monkeypatch.setattr("builtins.input", lambda *_: next(answers))

    assert PlainRenderer(registry).run(config) is Action.SAVE
    assert config["hostname"] == "edited"


def test_unknown_choice_does_not_leave_the_menu(monkeypatch) -> None:
    registry = build_registry()
    config = {"hostname": "framework", "disk": "/dev/nvme0n1"}
    answers = iter(["nonsense", "99", "q"])
    monkeypatch.setattr("builtins.input", lambda *_: next(answers))

    assert PlainRenderer(registry).run(config) is Action.ABORT


def test_renderer_selection_falls_back_to_plain(monkeypatch) -> None:
    from arch_framework import tui

    monkeypatch.setattr(tui, "textual_available", lambda: False)
    renderer = tui.select_renderer(build_registry())
    assert renderer.name == "plain"


def test_renderer_selection_honours_explicit_plain() -> None:
    from arch_framework import tui

    assert tui.select_renderer(build_registry(), prefer="plain").name == "plain"
