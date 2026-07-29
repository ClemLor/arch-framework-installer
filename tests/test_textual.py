"""Headless tests for the Textual renderer.

Textual is optional, so these skip when it is absent. They matter because the
plain renderer is what every other test drives: without them the Textual path
would be shipped unexecuted.
"""

from __future__ import annotations

import asyncio

import pytest

from arch_framework.lib.disk import DeviceHandler, FixtureSource
from arch_framework.profiles import default_config
from arch_framework.tui import textual_available
from arch_framework.tui.draft import Draft
from arch_framework.tui.entries import build_registry
from arch_framework.tui.menu import Action

pytestmark = pytest.mark.skipif(
    not textual_available(), reason="textual is not installed"
)


def build(framework_source: FixtureSource):
    draft = Draft(default_config())
    return draft, build_registry(draft, DeviceHandler(framework_source))


def run(coro):
    return asyncio.run(coro)


def test_app_mounts_and_lists_every_entry(framework_source: FixtureSource) -> None:
    from textual.widgets import ListView

    from arch_framework.tui.textual_app import MenuApp

    draft, registry = build(framework_source)
    app = MenuApp(registry, draft)

    async def scenario() -> int:
        async with app.run_test() as pilot:
            await pilot.pause()
            return len(pilot.app.query_one("#entries", ListView))

    assert run(scenario()) == len(registry.entries)


def test_abort_key_exits_with_abort(framework_source: FixtureSource) -> None:
    from arch_framework.tui.textual_app import MenuApp

    draft, registry = build(framework_source)
    app = MenuApp(registry, draft)

    async def scenario():
        async with app.run_test() as pilot:
            await pilot.press("q")
            await pilot.pause()
        return app.return_value

    assert run(scenario()) is Action.ABORT


def test_install_is_refused_while_mandatory_entries_are_unanswered(
    framework_source: FixtureSource,
) -> None:
    """The same guard as the plain renderer, enforced in the widget layer."""
    from arch_framework.tui.textual_app import MenuApp

    draft, registry = build(framework_source)
    app = MenuApp(registry, draft)

    async def scenario() -> str:
        async with app.run_test() as pilot:
            await pilot.press("i")
            await pilot.pause()
            return app.last_error

    message = run(scenario())
    assert "Disk configuration" in message
    assert app.return_value is None, "install must not have been accepted"


def test_install_accepted_once_answered(framework_source: FixtureSource) -> None:
    from arch_framework.tui.textual_app import MenuApp

    draft, registry = build(framework_source)
    for key in ("disk", "users"):
        draft.mark_answered(key)
    draft.update(
        lambda payload: payload["users"].update(
            users=[{"name": "clement", "sudo": True, "shell": "/usr/bin/fish", "groups": []}]
        )
    )
    app = MenuApp(registry, draft)

    async def scenario():
        async with app.run_test() as pilot:
            await pilot.press("i")
            await pilot.pause()
        return app.return_value

    assert run(scenario()) is Action.INSTALL


def test_closing_the_window_is_treated_as_abort(framework_source: FixtureSource) -> None:
    """A dismissed window is a refusal, never a licence to install."""
    from arch_framework.tui.textual_app import TextualRenderer

    draft, registry = build(framework_source)
    renderer = TextualRenderer(registry)

    class DeadApp:
        def run(self):
            return None

    renderer_module = __import__(
        "arch_framework.tui.textual_app", fromlist=["MenuApp"]
    )
    original = renderer_module.MenuApp
    renderer_module.MenuApp = lambda *_: DeadApp()  # type: ignore[assignment]
    try:
        assert renderer.run(draft) is Action.ABORT
    finally:
        renderer_module.MenuApp = original
