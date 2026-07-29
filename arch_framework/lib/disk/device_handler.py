"""Device enumeration and the destructive-action guard.

This is the code that stands between a configuration file and an erased disk.
Ported from the Bash implementation, where it was the only part worth keeping,
and kept independently testable: it reads through a
:class:`~arch_framework.lib.disk.source.DeviceSource` and never touches a block
device itself.

Four independent guards, each able to reject on its own:

* the device must be a whole disk, not a partition;
* it must not be the running live medium;
* it must not be attached over USB;
* it must not be marked removable.

They are deliberately separate. A single combined check would let one of them
break silently.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..models.device import DiskInfo, SafetyStatus, Transport
from ..models.size import Size
from .source import PARENT_KEY, DeviceSource, get_source, normalise_device_name

#: Mount points the Arch ISO uses, most specific first. The root filesystem is
#: the last resort because on an installed system it is the target itself.
LIVE_MEDIUM_MOUNTS: tuple[str, ...] = (
    "/run/archiso/bootmnt",
    "/run/archiso/cowspace",
    "/run/archiso",
)

#: Bound on the parent walk. A cycle should be impossible, but this code runs
#: immediately before destroying a disk, so it does not get to hang.
MAX_PARENT_DEPTH = 16


@dataclass(frozen=True)
class SafetyVerdict:
    status: SafetyStatus
    reason: str

    @property
    def writable(self) -> bool:
        return self.status is SafetyStatus.ELIGIBLE

    def __str__(self) -> str:
        if self.status is SafetyStatus.ELIGIBLE:
            return "Eligible"
        return f"{self.status.value}: {self.reason}"


def _mountpoints(record: dict[str, Any]) -> list[str]:
    """lsblk reports ``mountpoints`` as a list that contains nulls."""
    raw = record.get("mountpoints")
    if isinstance(raw, list):
        return [point for point in raw if isinstance(point, str) and point]

    single = record.get("mountpoint")
    return [single] if isinstance(single, str) and single else []


def _as_bool(value: Any) -> bool | None:
    """lsblk reports RM/ROTA as booleans in JSON but as 0/1 in older versions."""
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return bool(value)
    if isinstance(value, str) and value.strip() in {"0", "1"}:
        return value.strip() == "1"
    return None


class DeviceHandler:
    def __init__(self, source: DeviceSource | None = None) -> None:
        self.source = source or get_source()
        self._records: list[dict[str, Any]] | None = None

    # -- raw records --------------------------------------------------------

    def records(self, *, refresh: bool = False) -> list[dict[str, Any]]:
        if self._records is None or refresh:
            self._records = self.source.block_devices()
        return self._records

    def record(self, path: str) -> dict[str, Any] | None:
        wanted = normalise_device_name(path)
        for record in self.records():
            candidate = normalise_device_name(record.get("path") or record.get("name"))
            if candidate == wanted:
                return record
        return None

    def is_whole_disk(self, path: str) -> bool:
        record = self.record(path)
        return record is not None and record.get("type") == "disk"

    def exists(self, path: str) -> bool:
        return self.record(path) is not None

    # -- parent walk --------------------------------------------------------

    def parent_of(self, path: str) -> str | None:
        record = self.record(path)
        if record is None:
            return None

        parent = record.get(PARENT_KEY)
        if isinstance(parent, str) and parent:
            return parent

        # Fall back to lsblk's own field, in whichever form it reports.
        return normalise_device_name(record.get("pkname"))

    def resolve_parent_disk(self, path: str) -> str | None:
        """Walk up from any block device to the whole disk containing it.

        A device-mapper node on top of a partition needs two steps, hence the
        loop rather than a single lookup.
        """
        current = normalise_device_name(path)

        for _ in range(MAX_PARENT_DEPTH):
            if current is None:
                return None
            if self.is_whole_disk(current):
                return current

            parent = self.parent_of(current)
            if parent is None or parent == current:
                return None
            current = parent

        return None

    # -- live medium --------------------------------------------------------

    def live_medium_source(self) -> str | None:
        """The device the running ISO was booted from, if any."""
        for mountpoint in LIVE_MEDIUM_MOUNTS:
            if not self.source.path_exists(mountpoint):
                continue
            source = self.source.mount_source(mountpoint)
            if source and source.startswith("/dev/"):
                return source

        root = self.source.mount_source("/")
        if root and root.startswith("/dev/"):
            return root
        return None

    def live_medium_disk(self) -> str | None:
        source = self.live_medium_source()
        if source is None:
            return None
        return self.resolve_parent_disk(source)

    def is_live_medium(self, path: str) -> bool:
        live = self.live_medium_disk()
        return live is not None and normalise_device_name(path) == live

    # -- individual guards --------------------------------------------------

    def transport(self, path: str) -> Transport:
        record = self.record(path) or {}
        raw = record.get("tran")
        if isinstance(raw, str) and raw:
            try:
                return Transport(raw.lower())
            except ValueError:
                return Transport.UNKNOWN
        # NVMe devices sometimes report no transport at all.
        if (normalise_device_name(path) or "").startswith("/dev/nvme"):
            return Transport.NVME
        return Transport.UNKNOWN

    def is_usb(self, path: str) -> bool:
        return self.transport(path) is Transport.USB

    def is_removable(self, path: str) -> bool:
        return _as_bool((self.record(path) or {}).get("rm")) is True

    def mountpoints(self, path: str) -> list[str]:
        """Every mount point on the disk or any of its partitions."""
        wanted = normalise_device_name(path)
        found: list[str] = []
        for record in self.records():
            candidate = normalise_device_name(record.get("path") or record.get("name"))
            parent = record.get(PARENT_KEY)
            if candidate == wanted or parent == wanted:
                found.extend(_mountpoints(record))
        return found

    def has_luks(self, path: str) -> bool:
        wanted = normalise_device_name(path)
        for record in self.records():
            candidate = normalise_device_name(record.get("path") or record.get("name"))
            parent = record.get(PARENT_KEY)
            if candidate == wanted or parent == wanted:
                if record.get("fstype") == "crypto_LUKS":
                    return True
        return False

    # -- verdict ------------------------------------------------------------

    def safety(self, path: str, *, read_only_mode: bool = False) -> SafetyVerdict:
        """Classify a disk.

        ``read_only_mode`` covers ``--inspect``, ``--plan-storage`` and
        ``--dry-run``: a mounted disk is fine to look at and to generate a plan
        for, but must never be written to. It does not relax any other guard —
        the live medium stays refused in every mode.
        """
        if not self.exists(path):
            return SafetyVerdict(SafetyStatus.REJECTED, "device not found")

        if not self.is_whole_disk(path):
            return SafetyVerdict(SafetyStatus.REJECTED, "not a whole disk")

        if self.is_live_medium(path):
            return SafetyVerdict(SafetyStatus.REJECTED, "Arch live medium")

        if self.is_usb(path):
            return SafetyVerdict(SafetyStatus.REJECTED, "USB transport")

        if self.is_removable(path):
            return SafetyVerdict(SafetyStatus.REJECTED, "removable device")

        if self.mountpoints(path):
            if read_only_mode:
                return SafetyVerdict(SafetyStatus.WARNING, "mounted filesystems")
            return SafetyVerdict(SafetyStatus.REJECTED, "mounted filesystems")

        return SafetyVerdict(SafetyStatus.ELIGIBLE, "")

    def is_installation_candidate(self, path: str) -> bool:
        return self.safety(path).writable

    # -- listings -----------------------------------------------------------

    def disks(self) -> list[str]:
        return [
            normalise_device_name(record.get("path") or record.get("name")) or ""
            for record in self.records()
            if record.get("type") == "disk"
        ]

    def installation_candidates(self) -> list[str]:
        return [path for path in self.disks() if self.is_installation_candidate(path)]

    def info(self, path: str) -> DiskInfo | None:
        record = self.record(path)
        if record is None:
            return None

        raw_size = record.get("size")
        return DiskInfo(
            path=normalise_device_name(record.get("path") or record.get("name")) or path,
            model=record.get("model") or "Unknown",
            serial=record.get("serial") or "Unknown",
            size=Size.from_bytes(raw_size) if isinstance(raw_size, int) else None,
            transport=self.transport(path),
            removable=_as_bool(record.get("rm")),
            rotational=_as_bool(record.get("rota")),
            partition_table=record.get("pttype") or "none",
            logical_sector_size=record.get("log-sec"),
            physical_sector_size=record.get("phy-sec"),
            mountpoints=self.mountpoints(path),
            has_luks=self.has_luks(path),
            is_live_medium=self.is_live_medium(path),
        )
