"""The configuration, in the same vocabulary as the shell.

Field names map one-to-one onto the variables in ``config/system.conf``, and
nothing is renamed on the way through. A menu that spoke a different vocabulary
than the installer would need a translation table, and a translation table is a
third place for the three to disagree.

Reading is deliberately conservative: the file is Bash, but it is parsed rather
than executed. Sourcing it would run whatever it contains, and the configurator
has no business doing that.
"""

from __future__ import annotations

import re
import shlex
from dataclasses import dataclass, field, replace
from pathlib import Path

SIZE_PATTERN = re.compile(r"^([0-9]+)(MiB|GiB|TiB)$")
_MULTIPLIER = {"MiB": 1, "GiB": 1024, "TiB": 1024 * 1024}

#: Scalar assignment: NAME="value" or NAME=value.
_SCALAR = re.compile(r"^([A-Z_][A-Z0-9_]*)=(.*)$")
#: Array assignment opener: NAME=(
_ARRAY_OPEN = re.compile(r"^([A-Z_][A-Z0-9_]*)=\($")


@dataclass(frozen=True, order=True)
class Size:
    """A size in whole MiB, rendered back in the shell's own format."""

    mib: int

    @classmethod
    def parse(cls, value: str) -> "Size":
        match = SIZE_PATTERN.match(value.strip())
        if match is None:
            raise ValueError(
                f"unsupported size {value!r}: use 0GiB, 1024MiB, 32GiB or 1TiB"
            )
        number, unit = match.groups()
        return cls(int(number) * _MULTIPLIER[unit])

    def __str__(self) -> str:
        if self.mib == 0:
            return "0GiB"
        if self.mib % (1024 * 1024) == 0:
            return f"{self.mib // (1024 * 1024)}TiB"
        if self.mib % 1024 == 0:
            return f"{self.mib // 1024}GiB"
        return f"{self.mib}MiB"

    def human(self) -> str:
        if self.mib == 0:
            return "none"
        if self.mib >= 1024:
            return f"{self.mib / 1024:.1f} GiB"
        return f"{self.mib} MiB"


def parse_shell_config(text: str) -> dict[str, object]:
    """Extract assignments from a Bash configuration file without running it.

    Handles the two shapes the project uses: scalar assignments and
    parenthesised arrays. Anything else is ignored rather than guessed at.
    """
    values: dict[str, object] = {}
    lines = text.splitlines()
    index = 0

    while index < len(lines):
        line = lines[index].strip()
        index += 1

        if not line or line.startswith("#"):
            continue

        array_match = _ARRAY_OPEN.match(line)
        if array_match is not None:
            entries: list[str] = []
            while index < len(lines):
                inner = lines[index].strip()
                index += 1
                if inner.startswith(")"):
                    break
                inner = inner.split("#", 1)[0].strip()
                if inner:
                    entries.extend(shlex.split(inner))
            values[array_match.group(1)] = entries
            continue

        scalar_match = _SCALAR.match(line)
        if scalar_match is None:
            continue

        name, raw = scalar_match.groups()
        raw = raw.split(" #", 1)[0].strip()
        if not raw:
            values[name] = ""
            continue
        try:
            parts = shlex.split(raw)
        except ValueError:
            continue
        values[name] = parts[0] if parts else ""

    return values


def _as_bool(value: object, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() == "true"
    return default


@dataclass
class Configuration:
    """Everything the menu can change, plus the observed facts rules need."""

    # System
    hostname: str = "framework"
    timezone: str = "Europe/Zurich"
    locale: str = "en_US.UTF-8"
    keymap: str = "fr_CH"
    username: str = "user"
    user_shell: str = "/usr/bin/fish"

    # Storage
    target_disk: str = ""
    efi_size: Size = Size(1024)
    filesystem: str = "btrfs"
    btrfs_compression: str = "zstd"
    btrfs_subvolumes: list[str] = field(
        default_factory=lambda: ["@", "@home", "@snapshots", "@cache", "@log"]
    )

    # Encryption
    luks_enabled: bool = True
    tpm2_enabled: bool = True

    # Memory
    swap_size: Size = Size(0)
    zram_enabled: bool = True
    hibernation_enabled: bool = False

    # Boot
    default_kernel: str = "linux-lts"
    fallback_kernel: str = "linux"

    # Desktop
    desktop_autologin: bool = True

    # -- observed, not configurable -------------------------------------------
    #: Installed memory in MiB. Zero when unknown, which disables the rules that
    #: depend on it rather than letting them guess.
    memory_mib: int = 0
    #: Size of the selected disk in MiB. Zero when unknown.
    disk_size_mib: int = 0

    #: Settings the user has explicitly answered. The target disk needs this: the
    #: shipped configuration carries a plausible value, and a value nobody chose
    #: must not be installed onto.
    answered: set[str] = field(default_factory=set)

    # -- reading --------------------------------------------------------------

    @classmethod
    def from_shell(cls, values: dict[str, object]) -> "Configuration":
        def text(name: str, default: str) -> str:
            value = values.get(name)
            return value if isinstance(value, str) and value else default

        def size(name: str, default: Size) -> Size:
            value = values.get(name)
            if isinstance(value, str) and value:
                try:
                    return Size.parse(value)
                except ValueError:
                    return default
            return default

        subvolumes = values.get("BTRFS_SUBVOLUMES")
        if not isinstance(subvolumes, list) or not subvolumes:
            subvolumes = ["@", "@home", "@snapshots", "@cache", "@log"]

        return cls(
            hostname=text("HOSTNAME", "framework"),
            timezone=text("TIMEZONE", "Europe/Zurich"),
            locale=text("LOCALE", "en_US.UTF-8"),
            keymap=text("KEYMAP", "fr_CH"),
            username=text("USERNAME", "user"),
            user_shell=text("USER_SHELL", "/usr/bin/fish"),
            target_disk=text("TARGET_DISK", ""),
            efi_size=size("EFI_SIZE", Size(1024)),
            filesystem=text("FILESYSTEM", "btrfs"),
            btrfs_compression=text("BTRFS_COMPRESSION", "zstd"),
            btrfs_subvolumes=list(subvolumes),
            luks_enabled=_as_bool(values.get("LUKS_ENABLED"), True),
            tpm2_enabled=_as_bool(values.get("TPM2_ENABLED"), True),
            swap_size=size("SWAP_SIZE", Size(0)),
            zram_enabled=_as_bool(values.get("ZRAM_ENABLED"), True),
            hibernation_enabled=_as_bool(values.get("HIBERNATION_ENABLED"), False),
            default_kernel=text("DEFAULT_KERNEL", "linux-lts"),
            fallback_kernel=text("FALLBACK_KERNEL", "linux"),
            desktop_autologin=_as_bool(values.get("DESKTOP_AUTOLOGIN"), True),
        )

    @classmethod
    def load(cls, path: Path) -> "Configuration":
        return cls.from_shell(parse_shell_config(path.read_text(encoding="utf-8")))

    # -- editing --------------------------------------------------------------

    def with_value(self, field_name: str, value: object) -> "Configuration":
        """A copy with one field changed. Used to trial constraint outcomes."""
        copy = replace(self, **{field_name: value})  # type: ignore[arg-type]
        # replace() shares the mutable members, so a trial would otherwise edit
        # the real configuration's lists and sets.
        copy.btrfs_subvolumes = list(self.btrfs_subvolumes)
        copy.answered = set(self.answered)
        return copy

    def with_swap_size(self, size: "Size") -> "Configuration":
        """A copy with the swap size changed *and the layout that implies*.

        Selecting a swap size is what creates the @swap subvolume; the subvolume
        is not an independent choice the user has to make first. Trialling the
        size on its own would report every non-zero size as blocked for want of
        something the menu would have added.
        """
        copy = self.with_value("swap_size", size)

        if size.mib > 0:
            if "@swap" not in copy.btrfs_subvolumes:
                copy.btrfs_subvolumes.append("@swap")
        elif "@swap" in copy.btrfs_subvolumes:
            copy.btrfs_subvolumes.remove("@swap")

        return copy

    def apply_swap_size(self, size: "Size") -> str | None:
        """Commit a swap size, adjusting the subvolume set to match."""
        had_swap = "@swap" in self.btrfs_subvolumes
        updated = self.with_swap_size(size)

        self.swap_size = updated.swap_size
        self.btrfs_subvolumes = updated.btrfs_subvolumes
        self.answered.add("swap_size")

        has_swap = "@swap" in self.btrfs_subvolumes
        if has_swap and not had_swap:
            return "added the @swap subvolume (copy-on-write disabled)"
        if had_swap and not has_swap:
            return "removed the unused @swap subvolume"
        return None

    def set_hibernation(self, enabled: bool) -> str | None:
        """Toggle hibernation and bring the layout with it.

        Enabling hibernation without a swapfile and without @swap is invalid, and
        making the user discover that by being blocked would be a poor way to
        guide them. What changed is returned so it can be reported rather than
        happening silently.
        """
        self.hibernation_enabled = enabled
        notes: list[str] = []

        if enabled:
            if self.swap_size.mib == 0:
                # Round up to a whole GiB at or above RAM; below RAM the image
                # does not fit.
                needed = max(self.memory_mib, 8 * 1024)
                self.swap_size = Size(((needed + 1023) // 1024) * 1024)
                notes.append(f"swap set to {self.swap_size} to hold a memory image")
            if "@swap" not in self.btrfs_subvolumes:
                self.btrfs_subvolumes.append("@swap")
                notes.append("added the @swap subvolume (no copy-on-write)")
        else:
            if "@swap" in self.btrfs_subvolumes:
                self.btrfs_subvolumes.remove("@swap")
                notes.append("removed the unused @swap subvolume")
            if self.swap_size.mib > 0:
                self.swap_size = Size(0)
                notes.append("swap disabled; zram alone")

        self.answered.add("swap")
        return "; ".join(notes) if notes else None

    def set_encryption(self, enabled: bool) -> str | None:
        """Turning encryption off must also turn TPM2 off: there is nothing left
        for it to unlock, and validate_config refuses the combination."""
        self.luks_enabled = enabled
        if not enabled and self.tpm2_enabled:
            self.tpm2_enabled = False
            return "TPM2 disabled: it needs a LUKS container to unlock"
        return None

    # -- writing --------------------------------------------------------------

    def to_shell(self) -> str:
        """Render as a Bash fragment for install.sh to source.

        Only the settings the menu owns are emitted. Everything else stays in
        config/system.conf, so this file remains readable as a record of what was
        actually chosen.
        """
        lines = [
            "# Generated by the arch-framework-installer configurator.",
            "#",
            "# Sourced by lib/config.sh after config/system.conf, so these values",
            "# override the tracked defaults. Safe to delete: doing so returns the",
            "# installer to config/system.conf.",
            "",
            "# System",
            f'HOSTNAME="{self.hostname}"',
            f'TIMEZONE="{self.timezone}"',
            f'LOCALE="{self.locale}"',
            f'KEYMAP="{self.keymap}"',
            f'USERNAME="{self.username}"',
            f'USER_SHELL="{self.user_shell}"',
            "",
            "# Storage",
            f'TARGET_DISK="{self.target_disk}"',
            f'EFI_SIZE="{self.efi_size}"',
            f'FILESYSTEM="{self.filesystem}"',
            f'BTRFS_COMPRESSION="{self.btrfs_compression}"',
            "BTRFS_SUBVOLUMES=(",
        ]
        lines.extend(f'    "{subvolume}"' for subvolume in self.btrfs_subvolumes)
        lines.extend(
            [
                ")",
                "",
                "# Encryption",
                f'LUKS_ENABLED="{str(self.luks_enabled).lower()}"',
                f'TPM2_ENABLED="{str(self.tpm2_enabled).lower()}"',
                "",
                "# Memory",
                f'SWAP_SIZE="{self.swap_size}"',
                f'ZRAM_ENABLED="{str(self.zram_enabled).lower()}"',
                f'HIBERNATION_ENABLED="{str(self.hibernation_enabled).lower()}"',
                "",
                "# Boot",
                f'DEFAULT_KERNEL="{self.default_kernel}"',
                f'FALLBACK_KERNEL="{self.fallback_kernel}"',
                "",
                "# Desktop",
                f'DESKTOP_AUTOLOGIN="{str(self.desktop_autologin).lower()}"',
                "",
            ]
        )
        return "\n".join(lines)

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.to_shell(), encoding="utf-8")
