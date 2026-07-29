"""Bootloader selection.

Only Limine is supported, matching the Bash implementation and the project's
documented choice. The enum exists so adding another one later is a local
change rather than a search-and-replace.
"""

from __future__ import annotations

from enum import StrEnum


class Bootloader(StrEnum):
    LIMINE = "limine"

    @property
    def packages(self) -> tuple[str, ...]:
        match self:
            case Bootloader.LIMINE:
                return ("limine", "limine-mkinitcpio-hook")
