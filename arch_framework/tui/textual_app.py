"""Textual renderer.

Imported lazily, so a machine without Textual never pays for it.

Phase 1 scope: the menu itself — the entry list with inline current values,
mandatory markers, the Save/Install/Abort actions, and the guard that refuses
Install while a mandatory entry is unanswered. Editing an entry suspends the
application and runs that entry's own interaction on the terminal, which is
correct behaviour rather than a placeholder: it keeps a single implementation of
each prompt. Phase 3 replaces the suspend with modal screens where a modal
genuinely reads better, such as multi-select lists.
"""

from __future__ import annotations

from typing import Any

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.widgets import Footer, Header, ListItem, ListView, Static

from .menu import Action, MenuEntry, MenuRegistry


class MenuApp(App[Action]):
    CSS = """
    Screen { align: center middle; }
    #menu { width: 90%; height: auto; max-height: 80%; }
    #hint { padding: 1 2; color: $text-muted; }
    #error { padding: 0 2; color: $error; }
    """

    BINDINGS = [
        Binding("s", "save", "Save configuration"),
        Binding("i", "install", "Install"),
        Binding("q", "abort", "Abort"),
        Binding("enter", "edit", "Edit entry", priority=True),
    ]

    def __init__(self, registry: MenuRegistry, config: Any) -> None:
        super().__init__()
        self.registry = registry
        self.config = config

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        with Vertical(id="menu"):
            yield ListView(
                *(ListItem(Static(line)) for line in self._lines()),
                id="entries",
            )
            yield Static("* = required", id="hint")
            yield Static("", id="error")
        yield Footer()

    def on_mount(self) -> None:
        self.title = "Arch Framework Installer"
        self.sub_title = "Guided configuration"

    def _lines(self) -> list[str]:
        return self.registry.render_lines(self.config)

    def _refresh_entries(self) -> None:
        view = self.query_one("#entries", ListView)
        index = view.index
        view.clear()
        for line in self._lines():
            view.append(ListItem(Static(line)))
        if index is not None:
            view.index = index

    def _selected(self) -> MenuEntry | None:
        view = self.query_one("#entries", ListView)
        if view.index is None:
            return None
        return self.registry.entries[view.index]

    def _error(self, message: str) -> None:
        self.query_one("#error", Static).update(message)

    # -- actions ------------------------------------------------------------

    def action_edit(self) -> None:
        entry = self._selected()
        if entry is None or entry.edit is None:
            self._error("This entry is not editable.")
            return

        self._error("")
        # One implementation of each prompt, shared with the plain renderer.
        with self.suspend():
            print()
            if entry.help_text:
                print(f"{entry.help_text}\n")
            try:
                entry.edit(self.config)
            except (KeyboardInterrupt, EOFError):
                print("\nCancelled.")
            except ValueError as exc:
                print(f"\nRejected: {exc}")
                input("Press Enter to continue...")

        self._refresh_entries()

    def action_save(self) -> None:
        self.exit(Action.SAVE)

    def action_install(self) -> None:
        missing = self.registry.unanswered_mandatory(self.config)
        if missing:
            labels = ", ".join(entry.label for entry in missing)
            self._error(f"Required and unanswered: {labels}")
            return
        self.exit(Action.INSTALL)

    def action_abort(self) -> None:
        self.exit(Action.ABORT)


class TextualRenderer:
    name = "textual"

    def __init__(self, registry: MenuRegistry) -> None:
        self.registry = registry

    def run(self, config: Any) -> Action:
        result = MenuApp(self.registry, config).run()
        # A closed window is a refusal, not a licence to install.
        return result if result is not None else Action.ABORT
