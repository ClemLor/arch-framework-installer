"""Framework Laptop defaults.

Everything this project has already decided lives here rather than in a menu:
Btrfs, Limine, LUKS2 with TPM2, zstd compression, the subvolume set, the Swiss
French keyboard. The menu only asks about what genuinely varies between
installs, which is why it is shorter than archinstall's.
"""

from __future__ import annotations

from ..lib.models import (
    Bootloader,
    DiskConfig,
    EncryptionConfig,
    InstallConfig,
    LocaleConfig,
    PackageConfig,
    Size,
    SwapConfig,
    SystemConfig,
    UserConfig,
)
from ..lib.models.device import REQUIRED_SUBVOLUMES, SWAP_SUBVOLUME

#: A single placeholder target. The menu's disk entry is mandatory precisely so
#: this is never silently installed onto.
PLACEHOLDER_DISK = "/dev/nvme0n1"


def default_config(*, hibernation: bool = True) -> InstallConfig:
    subvolumes = list(REQUIRED_SUBVOLUMES)
    if hibernation:
        subvolumes.append(SWAP_SUBVOLUME)

    return InstallConfig(
        system=SystemConfig(
            hostname="framework",
            default_kernel="linux-lts",
            fallback_kernel="linux",
        ),
        locale=LocaleConfig(),
        disk=DiskConfig(
            target_disk=PLACEHOLDER_DISK,
            efi_size=Size.parse("1GiB"),
            minimum_disk_size=Size.parse("64GiB"),
            subvolumes=subvolumes,
        ),
        encryption=EncryptionConfig(
            enabled=True,
            mapper_name="cryptroot",
            tpm2_enabled=True,
        ),
        swap=SwapConfig(
            size=Size.parse("32GiB"),
            zram_enabled=True,
            hibernation_enabled=hibernation,
        ),
        packages=PackageConfig(),
        users=UserConfig(),
        bootloader=Bootloader.LIMINE,
    )
