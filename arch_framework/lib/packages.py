"""Package lists and installation.

Lists stay as plain ``packages/*.list`` files — one package per line, comments
allowed — because that format reviews well in a diff, which is how a decision
about what goes on the machine actually gets examined.

An empty or missing list is not an error: several groups are deliberately
unpopulated so far. Selecting one and getting nothing is reported rather than
silently ignored, so the gap is visible.
"""

from __future__ import annotations

from pathlib import Path

from . import log
from .command import CommandRunner, get_runner
from .exceptions import StageError
from .models import Bootloader, InstallConfig, PackageGroup

#: Repository root, three levels up from this file.
PACKAGE_DIRECTORY = Path(__file__).resolve().parent.parent.parent / "packages"


def read_list(group: PackageGroup, *, directory: Path | None = None) -> list[str]:
    path = (directory or PACKAGE_DIRECTORY) / f"{group.value}.list"

    if not path.is_file():
        return []

    packages: list[str] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].strip()
        if line:
            packages.append(line)
    return packages


def resolve(config: InstallConfig, *, directory: Path | None = None) -> list[str]:
    """Every package to install, deduplicated, in a stable order.

    Kernels, bootloader and encryption packages are added from the configuration
    rather than listed in a file: they follow from choices the user made, and
    duplicating them in a list is a way for the two to disagree.
    """
    packages: list[str] = []
    empty: list[str] = []

    for group in config.packages.groups:
        entries = read_list(group, directory=directory)
        if not entries:
            empty.append(group.value)
        packages.extend(entries)

    if empty:
        log.warn(f"These package groups are empty: {', '.join(empty)}")

    packages.extend(config.system.kernels)
    packages.extend(f"{kernel}-headers" for kernel in config.system.kernels)
    packages.extend(config.encryption.packages)
    packages.extend(config.swap.packages)
    packages.extend(Bootloader(config.bootloader).packages)
    packages.extend(config.packages.additional)

    return list(dict.fromkeys(packages))


def pacstrap(
    config: InstallConfig,
    target: Path,
    *,
    runner: CommandRunner | None = None,
    directory: Path | None = None,
) -> list[str]:
    runner = runner or get_runner()
    packages = resolve(config, directory=directory)

    if not packages:
        raise StageError("no packages to install; every selected group is empty")

    log.info(f"Installing {len(packages)} packages into {target}")
    # Streamed: pacstrap runs for minutes and can ask questions. Captured output
    # would look like a hang and hide the prompt.
    runner.run(["pacstrap", "-K", str(target), *packages], stream=True)
    log.success("Base system installed.")
    return packages
