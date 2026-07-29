"""Block-device facts and the storage layout.

:class:`DiskInfo` is what the device layer observes; :class:`DiskConfig` is what
the user asked for. Keeping them apart is what lets the whole safety layer be
tested from recorded fixtures with no block devices present.
"""

from __future__ import annotations

from enum import Enum, StrEnum

from pydantic import BaseModel, Field, field_validator

from .size import Size


class SafetyStatus(Enum):
    """Whether a disk may be installed onto.

    ``WARNING`` exists for the read-only modes: a mounted disk is fine to
    inspect and to generate a plan for, but must never be written to.
    """

    ELIGIBLE = "Eligible"
    WARNING = "Warning"
    REJECTED = "Rejected"


class Transport(StrEnum):
    NVME = "nvme"
    SATA = "sata"
    USB = "usb"
    UNKNOWN = "unknown"


class DiskInfo(BaseModel):
    """Observed properties of one whole disk."""

    path: str
    model: str = "Unknown"
    serial: str = "Unknown"
    size: Size | None = None
    transport: Transport = Transport.UNKNOWN
    removable: bool | None = None
    rotational: bool | None = None
    partition_table: str = "none"
    logical_sector_size: int | None = None
    physical_sector_size: int | None = None
    mountpoints: list[str] = Field(default_factory=list)
    has_luks: bool = False
    is_live_medium: bool = False

    @property
    def mounted(self) -> bool:
        return bool(self.mountpoints)


class BtrfsCompression(StrEnum):
    ZSTD = "zstd"
    NONE = "none"


class Filesystem(StrEnum):
    BTRFS = "btrfs"


#: Subvolumes every layout must define. ``@swap`` is deliberately absent: it is
#: required only when hibernation is enabled, so that hibernation stays a
#: choice rather than a structural obligation.
REQUIRED_SUBVOLUMES: tuple[str, ...] = ("@", "@home", "@snapshots", "@cache", "@log")

SWAP_SUBVOLUME = "@swap"


class DiskConfig(BaseModel):
    """The requested storage layout."""

    target_disk: str
    efi_size: Size = Size.parse("1GiB")
    efi_label: str = "EFI"
    system_label: str = "ARCH"
    minimum_disk_size: Size = Size.parse("64GiB")
    filesystem: Filesystem = Filesystem.BTRFS
    compression: BtrfsCompression = BtrfsCompression.ZSTD
    compression_level: int = Field(default=3, ge=0, le=15)
    subvolumes: list[str] = Field(default_factory=lambda: list(REQUIRED_SUBVOLUMES))

    @field_validator("target_disk")
    @classmethod
    def _absolute_device_path(cls, value: str) -> str:
        if not value.startswith("/dev/"):
            raise ValueError("target_disk must be an absolute device path under /dev")
        return value

    @field_validator("efi_label", "system_label")
    @classmethod
    def _label_charset(cls, value: str) -> str:
        if not value or not all(c.isalnum() or c in "_-" for c in value):
            raise ValueError(
                "partition labels may contain only letters, numbers, "
                "underscores and hyphens"
            )
        return value

    @field_validator("efi_size")
    @classmethod
    def _efi_bounds(cls, value: Size) -> Size:
        if value.mib < 512:
            raise ValueError("efi_size must be at least 512MiB")
        if value.mib > 4096:
            raise ValueError("efi_size must not exceed 4GiB")
        return value

    @field_validator("subvolumes")
    @classmethod
    def _required_subvolumes(cls, value: list[str]) -> list[str]:
        missing = [name for name in REQUIRED_SUBVOLUMES if name not in value]
        if missing:
            raise ValueError(f"missing required Btrfs subvolume(s): {', '.join(missing)}")
        return value

    # -- derived ------------------------------------------------------------

    def partition_path(self, number: int) -> str:
        """Partition device node for the target disk.

        NVMe, eMMC and loop devices insert a ``p`` before the number.
        """
        if self.target_disk.startswith(("/dev/nvme", "/dev/mmcblk", "/dev/loop")):
            return f"{self.target_disk}p{number}"
        return f"{self.target_disk}{number}"

    @property
    def efi_partition(self) -> str:
        return self.partition_path(1)

    @property
    def system_partition(self) -> str:
        return self.partition_path(2)

    @property
    def efi_end(self) -> Size:
        """End offset of the EFI partition; the first partition starts at 1MiB."""
        return Size(self.efi_size.mib + 1)

    @property
    def mount_options(self) -> str:
        if self.compression is BtrfsCompression.NONE:
            return "noatime"
        return f"noatime,compress={self.compression}:{self.compression_level}"
