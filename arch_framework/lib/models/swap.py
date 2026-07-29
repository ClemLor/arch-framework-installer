"""Swap and hibernation.

Hibernation needs a swapfile at least the size of RAM, living on a subvolume
with copy-on-write disabled and excluded from snapshots — otherwise a rollback
could restore a stale resume image over a running kernel's expectations.
"""

from __future__ import annotations

from pydantic import BaseModel

from .size import Size


class SwapConfig(BaseModel):
    size: Size = Size.parse("32GiB")
    zram_enabled: bool = True
    hibernation_enabled: bool = True

    @property
    def packages(self) -> tuple[str, ...]:
        return ("zram-generator",) if self.zram_enabled else ()

    def fits_ram(self, ram_bytes: int) -> bool:
        """Whether the swapfile can actually hold a hibernation image."""
        return self.size.bytes >= ram_bytes
