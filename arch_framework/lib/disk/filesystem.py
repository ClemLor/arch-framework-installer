"""Btrfs: creation, subvolumes, mounting, and the swapfile.

Mount order matters and is not alphabetical: ``@`` must be mounted first because
every other subvolume mounts inside it. The order is derived rather than
configured so it cannot be got wrong by editing a list.

The swapfile lives on ``@swap`` with copy-on-write disabled. A copy-on-write
swapfile corrupts, and a snapshot containing a resume image would let a rollback
restore a kernel image that no longer matches the running system.
"""

from __future__ import annotations

from pathlib import Path

from .. import log
from ..command import CommandRunner, get_runner
from ..models import DiskConfig, SwapConfig
from ..models.device import SWAP_SUBVOLUME

#: Where the target system is assembled.
MOUNT_ROOT = Path("/mnt")

#: Subvolume to mount point. Anything not listed is created but not mounted,
#: which is correct for @snapshots — snapper manages it inside the installed
#: system.
SUBVOLUME_MOUNTS: dict[str, str] = {
    "@": "",
    "@home": "home",
    "@cache": "var/cache",
    "@log": "var/log",
    SWAP_SUBVOLUME: "swap",
}

SWAPFILE_NAME = "swapfile"


def create_filesystem(
    disk: DiskConfig,
    mapper_path: str,
    *,
    runner: CommandRunner | None = None,
) -> None:
    runner = runner or get_runner()
    runner.run_critical(
        f"Creating the Btrfs filesystem on {mapper_path}",
        ["mkfs.btrfs", "--force", "--label", disk.system_label, mapper_path],
    )


def create_subvolumes(
    disk: DiskConfig,
    mapper_path: str,
    *,
    runner: CommandRunner | None = None,
) -> None:
    """Create every configured subvolume on a temporarily mounted top level."""
    runner = runner or get_runner()

    runner.run_critical(
        "Mounting the Btrfs top level",
        ["mount", mapper_path, str(MOUNT_ROOT)],
    )

    for subvolume in disk.subvolumes:
        runner.run_critical(
            f"Creating subvolume {subvolume}",
            ["btrfs", "subvolume", "create", str(MOUNT_ROOT / subvolume)],
        )

    if SWAP_SUBVOLUME in disk.subvolumes:
        # Disabling copy-on-write must happen while the subvolume is still
        # empty; setting it afterwards does not affect existing extents.
        runner.run_critical(
            f"Disabling copy-on-write on {SWAP_SUBVOLUME}",
            ["chattr", "+C", str(MOUNT_ROOT / SWAP_SUBVOLUME)],
        )

    runner.run_critical("Unmounting the top level", ["umount", str(MOUNT_ROOT)])


def mount_order(disk: DiskConfig) -> list[tuple[str, str]]:
    """Subvolumes to mount, root first, then by path depth.

    Derived rather than configured: a hand-maintained order would eventually
    place a nested mount before its parent.
    """
    entries = [
        (subvolume, SUBVOLUME_MOUNTS[subvolume])
        for subvolume in disk.subvolumes
        if subvolume in SUBVOLUME_MOUNTS
    ]
    return sorted(entries, key=lambda item: (item[1].count("/") + 1) if item[1] else 0)


def mount_commands(disk: DiskConfig, mapper_path: str) -> list[list[str]]:
    commands: list[list[str]] = []

    for subvolume, relative in mount_order(disk):
        target = MOUNT_ROOT / relative if relative else MOUNT_ROOT
        if relative:
            commands.append(["mkdir", "--parents", str(target)])
        commands.append(
            [
                "mount",
                "--options",
                f"subvol={subvolume},{disk.mount_options}",
                mapper_path,
                str(target),
            ]
        )

    commands.append(["mkdir", "--parents", str(MOUNT_ROOT / "boot")])
    commands.append(["mount", disk.efi_partition, str(MOUNT_ROOT / "boot")])
    return commands


def mount_all(
    disk: DiskConfig,
    mapper_path: str,
    *,
    runner: CommandRunner | None = None,
) -> None:
    runner = runner or get_runner()
    for argv in mount_commands(disk, mapper_path):
        runner.run_critical(" ".join(argv[:1] + argv[-1:]), argv)


def swapfile_commands(swap: SwapConfig) -> list[list[str]]:
    """Create the swapfile with btrfs' own helper.

    ``btrfs filesystem mkswapfile`` handles the no-copy-on-write and
    no-compression requirements that a plain ``dd`` plus ``mkswap`` does not.
    """
    path = MOUNT_ROOT / "swap" / SWAPFILE_NAME
    return [
        # Suffix is lowercase to match the documented k/m/g/e/p form.
        [
            "btrfs",
            "filesystem",
            "mkswapfile",
            "--size",
            f"{swap.size.mib}m",
            str(path),
        ],
        ["swapon", str(path)],
    ]


def create_swapfile(swap: SwapConfig, *, runner: CommandRunner | None = None) -> None:
    runner = runner or get_runner()
    for argv in swapfile_commands(swap):
        runner.run_critical(f"Swapfile: {argv[0]}", argv)


def resume_offset(*, runner: CommandRunner | None = None) -> str:
    """Physical offset of the swapfile, needed to resume from hibernation.

    Without it the kernel knows which device holds the image but not where, and
    resume silently falls back to a cold boot.
    """
    runner = runner or get_runner()
    path = MOUNT_ROOT / "swap" / SWAPFILE_NAME
    return runner.derived(
        ["btrfs", "inspect-internal", "map-swapfile", "--resume-offset", str(path)],
        placeholder="<resume-offset>",
    )


def unmount_all(*, runner: CommandRunner | None = None) -> None:
    runner = runner or get_runner()
    runner.run(["swapoff", "--all"], check=False)
    runner.run(["umount", "--recursive", str(MOUNT_ROOT)], check=False)
    log.info("Target filesystems unmounted.")
