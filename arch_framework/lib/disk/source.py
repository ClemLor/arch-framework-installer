"""Where device facts come from.

The safety logic is the most important code in this project and the hardest to
exercise: it only matters on a live ISO, as root, with real disks attached. So
it never touches the system directly — it asks a :class:`DeviceSource`.

``SystemSource`` shells out to ``lsblk --json`` and ``findmnt --json``.
``FixtureSource`` reads a file in exactly the same shape, which is how the
safety layer gets tested on a development machine with no block devices, and
how the TUI can be driven locally past its mandatory disk-configuration entry.

Record a fixture on a real machine with::

    lsblk --json --bytes --output-all > disks.json
    findmnt --json --list > mounts.json
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from .. import log
from ..command import get_runner

#: Set to a fixture file path to run against recorded devices instead of the
#: real machine. Also settable with --devices-from.
FIXTURE_ENV_VAR = "ARCH_FRAMEWORK_DEVICES"


@runtime_checkable
class DeviceSource(Protocol):
    """Read-only view of the host's block devices and mounts."""

    def block_devices(self) -> list[dict[str, Any]]:
        """Flat list of ``lsblk`` device records, children included."""

    def mount_source(self, target: str) -> str | None:
        """Device backing ``target``, or None when nothing is mounted there."""

    def read_text(self, path: str) -> str | None:
        """Contents of a sysfs/procfs file, or None when unreadable."""

    def path_exists(self, path: str) -> bool: ...


def _flatten(devices: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """lsblk nests partitions under their disk; the safety checks want both
    shapes, so children are kept *and* hoisted with a parent back-reference."""
    flat: list[dict[str, Any]] = []
    for device in devices:
        flat.append(device)
        for child in device.get("children") or []:
            child = dict(child)
            child.setdefault("pkname", device.get("name"))
            flat.extend(_flatten([child]))
    return flat


class SystemSource:
    """The real machine."""

    def block_devices(self) -> list[dict[str, Any]]:
        output = get_runner().capture(
            ["lsblk", "--json", "--bytes", "--paths", "--output-all"]
        )
        if not output.strip():
            return []
        try:
            payload = json.loads(output)
        except json.JSONDecodeError:
            log.warn("lsblk returned output that could not be parsed as JSON")
            return []
        return _flatten(payload.get("blockdevices") or [])

    def mount_source(self, target: str) -> str | None:
        output = get_runner().capture(
            ["findmnt", "--json", "--list", "--output", "SOURCE", "--target", target]
        )
        if not output.strip():
            return None
        try:
            payload = json.loads(output)
        except json.JSONDecodeError:
            return None
        entries = payload.get("filesystems") or []
        if not entries:
            return None
        source = entries[0].get("source")
        return source if isinstance(source, str) else None

    def read_text(self, path: str) -> str | None:
        try:
            return Path(path).read_text(encoding="utf-8", errors="replace")
        except OSError:
            return None

    def path_exists(self, path: str) -> bool:
        return Path(path).exists()


class FixtureSource:
    """Recorded devices, for tests and off-machine development.

    Fixture shape::

        {
          "blockdevices": [ ...lsblk --json records... ],
          "mounts":  {"/": "/dev/sdb1", "/run/archiso/bootmnt": "/dev/sdb1"},
          "files":   {"/sys/class/dmi/id/sys_vendor": "Framework\\n"},
          "paths":   ["/run/archiso", "/sys/firmware/efi/efivars"]
        }
    """

    def __init__(self, payload: dict[str, Any]) -> None:
        self._devices = _flatten(payload.get("blockdevices") or [])
        self._mounts: dict[str, str] = payload.get("mounts") or {}
        self._files: dict[str, str] = payload.get("files") or {}
        self._paths: set[str] = set(payload.get("paths") or [])
        self._paths.update(self._files)

    @classmethod
    def from_file(cls, path: str | Path) -> "FixtureSource":
        raw = Path(path).read_text(encoding="utf-8")
        return cls(json.loads(raw))

    def block_devices(self) -> list[dict[str, Any]]:
        return [dict(device) for device in self._devices]

    def mount_source(self, target: str) -> str | None:
        return self._mounts.get(target)

    def read_text(self, path: str) -> str | None:
        return self._files.get(path)

    def path_exists(self, path: str) -> bool:
        return path in self._paths


_source: DeviceSource | None = None


def get_source() -> DeviceSource:
    """Process-wide device source.

    Honours the fixture environment variable so tests and local TUI runs need
    no wiring beyond setting it.
    """
    global _source
    if _source is None:
        fixture = os.environ.get(FIXTURE_ENV_VAR)
        if fixture:
            log.warn(f"using recorded devices from {fixture}; not the real machine")
            _source = FixtureSource.from_file(fixture)
        else:
            _source = SystemSource()
    return _source


def set_source(source: DeviceSource | None) -> None:
    """Install a device source, or reset to autodetection with None."""
    global _source
    _source = source
