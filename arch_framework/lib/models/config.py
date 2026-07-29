"""The root configuration document.

This replaces ``config/system.conf`` and the ``validate_config`` arrays from the
Bash implementation. Adding a setting is now a one-file change instead of the
two-file edit that was easy to half-finish.

Rules that span several sections live here, because they cannot be expressed on
a single field:

* hibernation requires a ``@swap`` subvolume;
* the requested layout must leave a usable root filesystem behind.

The second one needs the real disk size, so it is a method taking the observed
size rather than a validator.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, model_validator

from ..exceptions import ConfigError
from .bootloader import Bootloader
from .device import SWAP_SUBVOLUME, DiskConfig
from .encryption import EncryptionConfig
from .locale import LocaleConfig, SystemConfig
from .packages import PackageConfig
from .size import Size
from .swap import SwapConfig
from .users import UserConfig

#: Smallest root filesystem this project treats as usable once EFI and swap are
#: carved out. A sanity floor, not a tuning knob.
MINIMUM_ROOT_SIZE = Size.parse("20GiB")


class InstallConfig(BaseModel):
    system: SystemConfig = Field(default_factory=SystemConfig)
    locale: LocaleConfig = Field(default_factory=LocaleConfig)
    disk: DiskConfig
    encryption: EncryptionConfig = Field(default_factory=EncryptionConfig)
    swap: SwapConfig = Field(default_factory=SwapConfig)
    packages: PackageConfig = Field(default_factory=PackageConfig)
    users: UserConfig = Field(default_factory=UserConfig)
    bootloader: Bootloader = Bootloader.LIMINE

    @model_validator(mode="after")
    def _hibernation_requires_swap_subvolume(self) -> "InstallConfig":
        if not self.swap.hibernation_enabled:
            return self

        if SWAP_SUBVOLUME not in self.disk.subvolumes:
            raise ValueError(
                f"hibernation requires the {SWAP_SUBVOLUME} subvolume: a swapfile "
                "must sit on a subvolume with copy-on-write disabled and excluded "
                "from snapshots"
            )
        return self

    # -- checks that need observed hardware ---------------------------------

    def root_size_for(self, disk_size: Size) -> Size:
        """Root filesystem left once EFI and swap are taken out."""
        return Size(disk_size.mib - self.disk.efi_size.mib - self.swap.size.mib)

    def validate_capacity(self, disk_size: Size) -> None:
        """Reject a layout that does not fit the real disk.

        ``minimum_disk_size`` on its own says nothing about whether the
        requested swapfile leaves anything behind — a 64GiB disk with a 32GiB
        swapfile passes that check while leaving roughly 31GiB of root.
        """
        if disk_size.mib == 0:
            raise ConfigError("unable to determine the target disk size")

        if disk_size < self.disk.minimum_disk_size:
            raise ConfigError(
                f"target disk is too small: {disk_size.human()} present, "
                f"{self.disk.minimum_disk_size} required"
            )

        root = self.root_size_for(disk_size)
        if root < MINIMUM_ROOT_SIZE:
            raise ConfigError(
                "the target disk cannot hold the planned layout: "
                f"{disk_size.human()} disk, {self.disk.efi_size} EFI, "
                f"{self.swap.size} swap leaves {root} for root, "
                f"below the {MINIMUM_ROOT_SIZE} floor"
            )

    def validate_hibernation(self, ram_bytes: int) -> None:
        """A swapfile smaller than RAM cannot hold a hibernation image."""
        if not self.swap.hibernation_enabled:
            return
        if not self.swap.fits_ram(ram_bytes):
            raise ConfigError(
                f"hibernation needs a swapfile of at least "
                f"{Size.from_bytes(ram_bytes)}; {self.swap.size} configured"
            )

    # -- persistence --------------------------------------------------------

    def to_json(self) -> str:
        """Serialise for saving. Deterministic, so a saved config diffs cleanly
        and two identical machines produce identical files."""
        return json.dumps(
            self.model_dump(mode="json"),
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
        )

    def save(self, path: Path) -> None:
        path.write_text(self.to_json() + "\n", encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> "InstallConfig":
        try:
            raw: Any = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise ConfigError(f"configuration file not found: {path}") from exc
        except json.JSONDecodeError as exc:
            raise ConfigError(f"{path} is not valid JSON: {exc}") from exc

        return cls.model_validate(raw)
