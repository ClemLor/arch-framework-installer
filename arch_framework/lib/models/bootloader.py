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
        """Packages installable during pacstrap, from the official repositories."""
        match self:
            case Bootloader.LIMINE:
                return ("limine",)

    @property
    def aur_packages(self) -> tuple[str, ...]:
        """Packages that exist only in the AUR.

        These cannot be installed during pacstrap: the AUR needs a helper and a
        build environment, neither of which exists in the live ISO. They are a
        post-first-boot step, and the installation must be able to boot without
        them.

        ``limine-mkinitcpio-hook`` automates regenerating boot entries when a
        kernel is installed or removed. Without it, ``limine.conf`` is written
        once by the installer and has to be maintained by hand.
        """
        match self:
            case Bootloader.LIMINE:
                return ("limine-mkinitcpio-hook",)
