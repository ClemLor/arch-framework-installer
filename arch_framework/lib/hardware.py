"""Host facts: firmware, CPU, memory, live-medium detection, Secure Boot.

Reads go through the device source, so this is exercisable from fixtures on a
machine that has no ``/sys/class/dmi`` at all.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .disk.source import DeviceSource, get_source
from .models.size import Size

_DMI = "/sys/class/dmi/id"


def _first_line(text: str | None) -> str | None:
    if text is None:
        return None
    line = text.strip()
    return line or None


@dataclass
class HostInfo:
    vendor: str = "Unknown"
    product: str = "Unknown"
    product_version: str = "Unknown"
    firmware_vendor: str = "Unknown"
    firmware_version: str = "Unknown"
    cpu: str = "Unknown"
    memory: Size | None = None
    uefi: bool = False
    secure_boot: str = "Unknown"
    live_environment: bool = False

    @property
    def machine(self) -> str:
        if self.product_version not in ("Unknown", self.product):
            return f"{self.product} {self.product_version}"
        return self.product

    @property
    def is_framework(self) -> bool:
        return self.vendor.lower().startswith("framework")


class Hardware:
    def __init__(self, source: DeviceSource | None = None) -> None:
        self.source = source or get_source()

    # -- identity -----------------------------------------------------------

    def vendor(self) -> str:
        return _first_line(self.source.read_text(f"{_DMI}/sys_vendor")) or "Unknown"

    def product(self) -> str:
        return _first_line(self.source.read_text(f"{_DMI}/product_name")) or "Unknown"

    def product_version(self) -> str:
        return (
            _first_line(self.source.read_text(f"{_DMI}/product_version")) or "Unknown"
        )

    def firmware_vendor(self) -> str:
        return _first_line(self.source.read_text(f"{_DMI}/bios_vendor")) or "Unknown"

    def firmware_version(self) -> str:
        return _first_line(self.source.read_text(f"{_DMI}/bios_version")) or "Unknown"

    def cpu(self) -> str:
        text = self.source.read_text("/proc/cpuinfo")
        if not text:
            return "Unknown"
        for line in text.splitlines():
            if line.startswith("model name"):
                _, _, value = line.partition(":")
                return value.strip() or "Unknown"
        return "Unknown"

    def memory(self) -> Size | None:
        text = self.source.read_text("/proc/meminfo")
        if not text:
            return None
        match = re.search(r"^MemTotal:\s+(\d+) kB", text, re.MULTILINE)
        if match is None:
            return None
        return Size.from_bytes(int(match.group(1)) * 1024)

    # -- boot state ---------------------------------------------------------

    def is_uefi(self) -> bool:
        return self.source.path_exists("/sys/firmware/efi/efivars")

    def secure_boot_state(self) -> str:
        """Read from the SecureBoot efivar.

        The variable is a 4-byte attribute prefix followed by one data byte, so
        the state is byte 4 — not byte 0.
        """
        if not self.is_uefi():
            return "Unavailable"

        raw = self.source.read_text(
            "/sys/firmware/efi/efivars/SecureBoot-8be4df61-93ca-11d2-aa0d-00e098032b8c"
        )
        if raw is None or len(raw) < 5:
            return "Unknown"

        return {"\x01": "Enabled", "\x00": "Disabled"}.get(raw[4], "Unknown")

    def is_live_environment(self) -> bool:
        """Whether this is a booted Arch ISO.

        ``/run/archiso`` is the reliable marker. The overlay/squashfs check is a
        fallback for a customised ISO that mounts things differently but is
        still a live medium.
        """
        if self.source.path_exists("/run/archiso"):
            return True

        if not self.source.path_exists("/etc/arch-release"):
            return False

        root = self.source.mount_source("/") or ""
        return root.startswith(("overlay", "airootfs")) or root.endswith(".squashfs")

    # -- aggregate ----------------------------------------------------------

    def info(self) -> HostInfo:
        return HostInfo(
            vendor=self.vendor(),
            product=self.product(),
            product_version=self.product_version(),
            firmware_vendor=self.firmware_vendor(),
            firmware_version=self.firmware_version(),
            cpu=self.cpu(),
            memory=self.memory(),
            uefi=self.is_uefi(),
            secure_boot=self.secure_boot_state(),
            live_environment=self.is_live_environment(),
        )
