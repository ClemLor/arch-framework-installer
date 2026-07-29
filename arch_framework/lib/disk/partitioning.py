"""GPT partitioning.

Two partitions, which is the whole layout: an EFI system partition and one
system partition holding everything else, encrypted.

The safety check is repeated here, immediately before the first destructive
command, rather than trusted from the menu. A configuration can be hand-written,
copied between machines, or replayed months later against different hardware —
the check that matters is the one taken against the disk as it is now.
"""

from __future__ import annotations

from ..command import CommandRunner, get_runner
from ..exceptions import UnsafeTargetError
from ..models import DiskConfig
from .device_handler import DeviceHandler

#: GPT type codes. ef00 is the EFI system partition; 8309 is
#: "Linux LUKS", which marks the partition for what it is even before it
#: contains a header.
EFI_TYPE_CODE = "ef00"
LUKS_TYPE_CODE = "8309"

#: Alignment start for the first partition.
FIRST_PARTITION_START = "1M"


def guard_target(config: DiskConfig, handler: DeviceHandler | None = None) -> None:
    """Refuse to continue unless the target is safe to destroy right now.

    Raises rather than warns. Everything after this point is unrecoverable.
    """
    handler = handler or DeviceHandler()
    verdict = handler.safety(config.target_disk)

    if not verdict.writable:
        raise UnsafeTargetError(
            f"refusing to partition {config.target_disk}: {verdict}"
        )


def partition_commands(config: DiskConfig) -> list[list[str]]:
    """The exact command sequence, as data.

    Separated from execution so it can be asserted against a golden file. The
    units are the point: sgdisk accepts K/M/G/T/P, where M already means MiB,
    and rejects "MiB" outright.
    """
    disk = config.target_disk
    efi_end = config.efi_end.sgdisk()

    return [
        ["wipefs", "--all", disk],
        ["sgdisk", "--zap-all", disk],
        [
            "sgdisk",
            f"--new=1:{FIRST_PARTITION_START}:{efi_end}",
            f"--typecode=1:{EFI_TYPE_CODE}",
            f"--change-name=1:{config.efi_label}",
            disk,
        ],
        [
            "sgdisk",
            f"--new=2:{efi_end}:0",
            f"--typecode=2:{LUKS_TYPE_CODE}",
            f"--change-name=2:{config.system_label}",
            disk,
        ],
        ["partprobe", disk],
    ]


def partition(
    config: DiskConfig,
    *,
    runner: CommandRunner | None = None,
    handler: DeviceHandler | None = None,
) -> None:
    runner = runner or get_runner()
    guard_target(config, handler)

    descriptions = [
        f"Erasing existing signatures on {config.target_disk}",
        "Clearing the partition table",
        f"Creating the EFI partition ({config.efi_size})",
        "Creating the system partition",
        "Re-reading the partition table",
    ]

    for description, argv in zip(descriptions, partition_commands(config), strict=True):
        runner.run_critical(description, argv)


def format_efi(config: DiskConfig, *, runner: CommandRunner | None = None) -> None:
    runner = runner or get_runner()
    runner.run_critical(
        f"Formatting {config.efi_partition} as FAT32",
        ["mkfs.fat", "-F32", "-n", config.efi_label, config.efi_partition],
    )
