"""Disk enumeration for the menu.

This exists to *show* the user which disks are usable and why the others are not.
It is not the safety gate — ``validate_partition_target_safety`` in
``lib/disk.sh`` is, and it runs on the live ISO immediately before anything
destructive. Duplicating the reasoning here is worth it anyway: a disk that
quietly does not appear in a list is worse than one shown as
"Rejected: Arch live medium".

Reads ``lsblk --json``. A recorded fixture can be substituted so the menu can be
exercised on a machine that has no such disks.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

#: Point at a recorded `lsblk --json --bytes --paths --output-all` capture.
FIXTURE_ENV_VAR = "AFI_DEVICES_FIXTURE"

#: Mount points the Arch ISO uses, most specific first. The root filesystem is
#: last because on an installed system it is the target itself.
LIVE_MEDIUM_MOUNTS = (
    "/run/archiso/bootmnt",
    "/run/archiso/cowspace",
    "/run/archiso",
)


@dataclass
class Disk:
    path: str
    model: str
    size_mib: int
    transport: str
    removable: bool
    is_live_medium: bool
    mountpoints: list[str]

    @property
    def eligible(self) -> bool:
        return self.rejection is None

    @property
    def rejection(self) -> str | None:
        """Why this disk cannot be installed onto, if it cannot."""
        if self.is_live_medium:
            return "Arch live medium"
        if self.transport == "usb":
            return "USB transport"
        if self.removable:
            return "removable device"
        return None

    @property
    def warning(self) -> str | None:
        """Something to know about an otherwise eligible disk."""
        if self.eligible and self.mountpoints:
            return f"mounted at {', '.join(self.mountpoints)}"
        return None

    def describe(self) -> str:
        size = f"{self.size_mib / 1024:.0f} GiB" if self.size_mib else "unknown size"
        parts = [size, self.model or "Unknown", self.transport or "unknown"]
        detail = ", ".join(part for part in parts if part)

        if self.rejection:
            return f"{detail} — Rejected: {self.rejection}"
        if self.warning:
            return f"{detail} — Warning: {self.warning}"
        return detail


def _mountpoints(record: dict) -> list[str]:
    raw = record.get("mountpoints")
    if isinstance(raw, list):
        return [point for point in raw if isinstance(point, str) and point]
    single = record.get("mountpoint")
    return [single] if isinstance(single, str) and single else []


def _flatten(records: list[dict]) -> list[dict]:
    flat: list[dict] = []
    for record in records:
        flat.append(record)
        flat.extend(_flatten(record.get("children") or []))
    return flat


def _load() -> list[dict]:
    fixture = os.environ.get(FIXTURE_ENV_VAR)
    if fixture:
        payload = json.loads(Path(fixture).read_text(encoding="utf-8"))
        return payload.get("blockdevices") or []

    if shutil.which("lsblk") is None:
        return []

    completed = subprocess.run(
        ["lsblk", "--json", "--bytes", "--paths", "--output-all"],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0 or not completed.stdout.strip():
        return []

    try:
        return json.loads(completed.stdout).get("blockdevices") or []
    except json.JSONDecodeError:
        return []


def _live_medium_disk(top_level: list[dict]) -> str | None:
    """Which whole disk the running ISO was booted from.

    Matched by mount point rather than by device name: the ISO's root is an
    overlay, so only the bootmnt mount identifies the physical stick.
    """
    for disk in top_level:
        for record in _flatten([disk]):
            for mountpoint in _mountpoints(record):
                if mountpoint in LIVE_MEDIUM_MOUNTS:
                    return disk.get("path") or disk.get("name")
    return None


def enumerate_disks() -> list[Disk]:
    top_level = [record for record in _load() if record.get("type") == "disk"]
    live = _live_medium_disk(top_level)

    disks: list[Disk] = []
    for record in top_level:
        path = record.get("path") or record.get("name") or ""
        size = record.get("size")
        mounts: list[str] = []
        for child in _flatten([record]):
            mounts.extend(_mountpoints(child))

        disks.append(
            Disk(
                path=path,
                model=(record.get("model") or "").strip(),
                size_mib=int(size) // (1024 * 1024) if isinstance(size, int) else 0,
                transport=(record.get("tran") or "").lower(),
                removable=bool(record.get("rm")),
                is_live_medium=path == live,
                mountpoints=mounts,
            )
        )
    return disks


def memory_mib() -> int:
    """Installed memory, or zero when it cannot be read.

    Zero rather than a guess: the hibernation sizing rule is disabled when the
    value is unknown, which is better than comparing against a fiction.
    """
    try:
        text = Path("/proc/meminfo").read_text(encoding="utf-8")
    except OSError:
        return 0

    for line in text.splitlines():
        if line.startswith("MemTotal:"):
            parts = line.split()
            if len(parts) >= 2 and parts[1].isdigit():
                return int(parts[1]) // 1024
    return 0
