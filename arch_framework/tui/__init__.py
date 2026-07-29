"""Renderers for the guided configuration menu.

Textual is present on the Arch ISO only because ``archinstall`` depends on it.
That is a transitive guarantee: archinstall has already migrated its interface
once, and if it migrates again the ISO stops shipping Textual — possibly on a
machine with no network, which is exactly when the installer must still work.
So availability is checked at runtime and the plain renderer is a first-class
path, not an apology.
"""

from __future__ import annotations

import importlib.util
import os
import sys
from typing import Any, Protocol

from .menu import Action, MenuEntry, MenuRegistry
from .plain import PlainRenderer

#: Set to force a renderer: "plain" or "textual".
RENDERER_ENV_VAR = "ARCH_FRAMEWORK_RENDERER"


class Renderer(Protocol):
    name: str

    def run(self, config: Any) -> Action: ...


def textual_available() -> bool:
    return importlib.util.find_spec("textual") is not None


def select_renderer(registry: MenuRegistry, *, prefer: str | None = None) -> Renderer:
    """Pick a renderer, honouring an explicit preference and the environment."""
    requested = prefer or os.environ.get(RENDERER_ENV_VAR)

    if requested == "plain":
        return PlainRenderer(registry)

    if requested == "textual":
        if not textual_available():
            raise RuntimeError("textual was requested but is not installed")
        return _textual(registry)

    # A non-interactive stdin cannot drive either renderer's prompts, but the
    # plain one at least degrades to a readable error instead of a curses crash.
    if not sys.stdin.isatty():
        return PlainRenderer(registry)

    if textual_available():
        return _textual(registry)

    return PlainRenderer(registry)


def _textual(registry: MenuRegistry) -> Renderer:
    from .textual_app import TextualRenderer

    return TextualRenderer(registry)


__all__ = [
    "RENDERER_ENV_VAR",
    "Action",
    "MenuEntry",
    "MenuRegistry",
    "PlainRenderer",
    "Renderer",
    "select_renderer",
    "textual_available",
]
