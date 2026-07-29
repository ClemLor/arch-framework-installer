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

import base64
import json
import os
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from .. import log
from ..command import get_runner

#: Set to a fixture file path to run against recorded devices instead of the
#: real machine. Also settable with --devices-from.
FIXTURE_ENV_VAR = "ARCH_FRAMEWORK_DEVICES"


#: Key holding the parent device path, recorded by :func:`flatten`.
#:
#: lsblk's own ``pkname`` is not relied on. It is documented as the "internal
#: parent kernel device name" and it is not established whether ``--paths``
#: prefixes it, so a value read from it could be ``sdb`` or ``/dev/sdb``
#: depending on the version. Recording the parent ourselves removes the
#: question; ``normalise_device_name`` handles the ambiguity wherever lsblk's
#: own field still has to be read.
PARENT_KEY = "_parent"


@runtime_checkable
class DeviceSource(Protocol):
    """Read-only view of the host's block devices and mounts."""

    def block_devices(self) -> list[dict[str, Any]]:
        """Flat list of ``lsblk`` device records, children included."""

    def mount_source(self, target: str) -> str | None:
        """Device backing ``target``, or None when nothing is mounted there."""

    def read_text(self, path: str) -> str | None:
        """Contents of a sysfs/procfs file, or None when unreadable."""

    def read_bytes(self, path: str) -> bytes | None:
        """Raw contents of a file. Needed for efivars, which are binary."""

    def path_exists(self, path: str) -> bool: ...


def normalise_device_name(value: str | None) -> str | None:
    """Return a ``/dev/``-prefixed path for a device name in either form."""
    if not value:
        return None
    if value.startswith("/dev/"):
        return value
    return f"/dev/{value}"


def flatten(devices: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Hoist nested partitions into a flat list.

    lsblk nests partitions under their disk. The safety checks need to walk
    both directions, so children are hoisted and each one records its parent's
    path under :data:`PARENT_KEY`.
    """
    flat: list[dict[str, Any]] = []
    for device in devices:
        parent = normalise_device_name(device.get("path") or device.get("name"))
        flat.append(device)
        for child in device.get("children") or []:
            child = dict(child)
            child[PARENT_KEY] = parent
            flat.extend(flatten([child]))
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
        return flatten(payload.get("blockdevices") or [])

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

    def read_bytes(self, path: str) -> bytes | None:
        try:
            return Path(path).read_bytes()
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
          "files_base64": {"/sys/firmware/efi/efivars/SecureBoot-...": "BgAAAAE="},
          "paths":   ["/run/archiso", "/sys/firmware/efi/efivars"]
        }

    ``files_base64`` exists because efivars are binary. A byte sequence that is
    not valid UTF-8 cannot survive storage as a JSON string, and decoding it
    with replacement characters collapses runs of bytes into single code points,
    shifting the offsets a caller indexes into.
    """

    def __init__(self, payload: dict[str, Any]) -> None:
        self._devices = flatten(payload.get("blockdevices") or [])
        self._mounts: dict[str, str] = payload.get("mounts") or {}
        self._files: dict[str, str] = payload.get("files") or {}
        self._binary: dict[str, bytes] = {
            path: base64.b64decode(value)
            for path, value in (payload.get("files_base64") or {}).items()
        }
        self._paths: set[str] = set(payload.get("paths") or [])
        self._paths.update(self._files)
        self._paths.update(self._binary)

    @classmethod
    def from_file(cls, path: str | Path) -> "FixtureSource":
        raw = Path(path).read_text(encoding="utf-8")
        return cls(json.loads(raw))

    def block_devices(self) -> list[dict[str, Any]]:
        return [dict(device) for device in self._devices]

    def mount_source(self, target: str) -> str | None:
        return self._mounts.get(target)

    def read_text(self, path: str) -> str | None:
        if path in self._files:
            return self._files[path]
        if path in self._binary:
            return self._binary[path].decode("utf-8", errors="replace")
        return None

    def read_bytes(self, path: str) -> bytes | None:
        if path in self._binary:
            return self._binary[path]
        if path in self._files:
            return self._files[path].encode("utf-8")
        return None

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
