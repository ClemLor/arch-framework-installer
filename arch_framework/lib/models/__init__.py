"""Configuration models.

Importing this package must not touch the system: no block devices, no root, no
Linux-only modules. That is what lets the models and the TUI be developed and
tested on a non-Linux machine.
"""

from .bootloader import Bootloader
from .config import MINIMUM_ROOT_SIZE, InstallConfig
from .device import (
    REQUIRED_SUBVOLUMES,
    SWAP_SUBVOLUME,
    BtrfsCompression,
    DiskConfig,
    DiskInfo,
    Filesystem,
    SafetyStatus,
    Transport,
)
from .encryption import EncryptionConfig
from .locale import LocaleConfig, SystemConfig
from .packages import MANDATORY_GROUPS, PackageConfig, PackageGroup
from .size import Size
from .swap import SwapConfig
from .users import Credentials, User, UserConfig

__all__ = [
    "MANDATORY_GROUPS",
    "MINIMUM_ROOT_SIZE",
    "REQUIRED_SUBVOLUMES",
    "SWAP_SUBVOLUME",
    "Bootloader",
    "BtrfsCompression",
    "Credentials",
    "DiskConfig",
    "DiskInfo",
    "EncryptionConfig",
    "Filesystem",
    "InstallConfig",
    "LocaleConfig",
    "PackageConfig",
    "PackageGroup",
    "SafetyStatus",
    "Size",
    "SwapConfig",
    "SystemConfig",
    "Transport",
    "User",
    "UserConfig",
]
