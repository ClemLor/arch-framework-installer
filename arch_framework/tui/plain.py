"""Plain-prompt renderer.

Not only a fallback for when Textual is missing. It is also the renderer that
works over a serial console, over SSH into the live ISO, and under a screen
reader, and it is the only one that can be driven from a script. Textual is a
nicer face on the same registry, not a replacement for this.
"""

from __future__ import annotations

from typing import Any

from .menu import Action, MenuRegistry


class PlainRenderer:
    name = "plain"

    def __init__(self, registry: MenuRegistry) -> None:
        self.registry = registry

    def run(self, config: Any) -> Action:
        while True:
            self._draw(config)
            choice = input("> ").strip().lower()

            if choice in {"q", "abort"}:
                return Action.ABORT
            if choice in {"s", "save"}:
                return Action.SAVE
            if choice in {"i", "install"}:
                missing = self.registry.unanswered_mandatory(config)
                if missing:
                    labels = ", ".join(entry.label for entry in missing)
                    print(f"\nCannot install yet. Required and unanswered: {labels}\n")
                    continue
                return Action.INSTALL

            entry = self._resolve(choice)
            if entry is None:
                print("\nUnrecognised choice.\n")
                continue
            if entry.edit is None:
                print(f"\n{entry.label} is not editable yet.\n")
                continue

            if entry.help_text:
                print(f"\n{entry.help_text}")
            entry.edit(config)

    def _resolve(self, choice: str):
        if choice.isdigit():
            index = int(choice) - 1
            if 0 <= index < len(self.registry.entries):
                return self.registry.entries[index]
            return None
        return self.registry.get(choice)

    def _draw(self, config: Any) -> None:
        print("\nArch Framework Installer\n")
        for number, line in enumerate(self.registry.render_lines(config), start=1):
            print(f"  {number:>2}) {line}")
        print("\n   s) Save configuration    i) Install    q) Abort")
        print("   * = required\n")
