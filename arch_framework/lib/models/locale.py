"""Locale, keymap and timezone.

Defaults come from the Bash configuration: an English system with a Swiss
French secondary locale and a Swiss French keyboard, which is what the target
machine actually needs.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class LocaleConfig(BaseModel):
    locale: str = "en_US.UTF-8"
    secondary_locale: str | None = "fr_CH.UTF-8"
    #: Console keymap, as found under /usr/share/kbd/keymaps.
    keymap: str = "fr_CH"
    #: X11/Wayland layout, which uses different names from the console keymap.
    xkb_layout: str = "ch"
    xkb_variant: str = "fr_nodeadkeys"
    timezone: str = "Europe/Zurich"
    ntp: bool = True

    @property
    def locales(self) -> list[str]:
        """Every locale that must be generated, in locale.gen order."""
        entries = [self.locale]
        if self.secondary_locale and self.secondary_locale != self.locale:
            entries.append(self.secondary_locale)
        return entries


class SystemConfig(BaseModel):
    #: RFC 1123 label: lowercase, no leading hyphen, 63 characters at most.
    hostname: str = Field(default="framework", pattern=r"^[a-z0-9][a-z0-9-]{0,62}$")
    default_kernel: str = "linux-lts"
    fallback_kernel: str | None = "linux"

    @property
    def kernels(self) -> list[str]:
        entries = [self.default_kernel]
        if self.fallback_kernel and self.fallback_kernel != self.default_kernel:
            entries.append(self.fallback_kernel)
        return entries
