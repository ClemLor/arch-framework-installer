"""What can be installed, and which components can be swapped.

Everything here is read from the repository rather than hardcoded: the package
groups come from ``packages/*.list``, the AUR packages from ``packages/aur.list``,
and the available bootloaders and desktop sessions from the
``SUPPORTED_*`` arrays in ``lib/provider.sh``.

That is deliberate. A menu with its own copy of the list would have to be edited
in step with the shell every time a package or a provider is added, and the two
would drift. Adding a bootloader means adding ``bootloader_<name>_*`` functions
and listing the name once; it then appears here without this file changing.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PACKAGES_DIRECTORY = PROJECT_ROOT / "packages"
PROVIDER_MODULE = PROJECT_ROOT / "lib" / "provider.sh"
PACSTRAP_MODULE = PROJECT_ROOT / "lib" / "pacstraps.sh"

#: Groups without which the result does not boot or cannot be repaired. Shown in
#: the menu as permanently ticked rather than hidden, so the set is visible.
MANDATORY_GROUPS = ("base", "firmware", "framework")

GROUP_DESCRIPTIONS: dict[str, str] = {
    "base": "base system, recovery tools, networking",
    "firmware": "microcode and device firmware",
    "framework": "Framework-specific firmware, TPM2, power",
    "desktop": "Wayland session, portals, audio",
    "development": "toolchains and language runtimes",
    "fonts": "text, monospace and emoji fonts",
    "multimedia": "codecs, players, image tools",
    "optional": "everything else worth having",
}


def _read_bash_array(text: str, name: str) -> list[str]:
    """Extract a `name=(a b c)` array from a Bash source file.

    Parsed, not executed: running lib/provider.sh to find out what it supports
    would mean running the installer's code to draw a menu.
    """
    match = re.search(rf"^\s*(?:readonly\s+)?{name}=\(([^)]*)\)", text, re.MULTILINE)
    if match is None:
        return []
    return [entry.strip().strip("'\"") for entry in match.group(1).split() if entry.strip()]


def read_package_list(path: Path) -> list[str]:
    if not path.is_file():
        return []

    packages: list[str] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].strip()
        if line:
            packages.append(line)
    return packages


@dataclass(frozen=True)
class Group:
    name: str
    packages: list[str]
    mandatory: bool

    @property
    def description(self) -> str:
        detail = GROUP_DESCRIPTIONS.get(self.name, "")
        count = f"{len(self.packages)} package{'s' if len(self.packages) != 1 else ''}"
        if not self.packages:
            # An empty group is shown rather than hidden: selecting one and
            # getting nothing should be visible, not silent.
            return f"{self.name} — empty"
        if detail:
            return f"{self.name} — {detail} ({count})"
        return f"{self.name} ({count})"


def package_groups() -> list[Group]:
    """Every group the shell knows about, in the shell's own order."""
    text = PACSTRAP_MODULE.read_text(encoding="utf-8")
    names = _read_bash_array(text, "AVAILABLE_PACKAGE_GROUPS")

    if not names:
        # Fall back to whatever lists exist, so a renamed variable degrades to a
        # usable menu instead of an empty one.
        names = sorted(
            path.stem
            for path in PACKAGES_DIRECTORY.glob("*.list")
            if path.stem != "aur"
        )

    return [
        Group(
            name=name,
            packages=read_package_list(PACKAGES_DIRECTORY / f"{name}.list"),
            mandatory=name in MANDATORY_GROUPS,
        )
        for name in names
    ]


@dataclass(frozen=True)
class AurPackage:
    name: str
    #: Trailing comment on the package's own line.
    note: str = ""

    @property
    def description(self) -> str:
        return f"{self.name} — {self.note}" if self.note else self.name


def aur_packages() -> list[AurPackage]:
    """AUR packages, described by the trailing comment on their own line.

        librewolf-bin  # Firefox without telemetry

    Only same-line comments are read. Standalone comments are for whoever is
    reading the file — section headings, longer rationale — and are ignored here,
    because guessing which of them was meant as a one-line description produces
    results like "librewolf-bin — Browsers".

    The shell strips everything from `#` onwards, so this costs nothing there.
    """
    path = PACKAGES_DIRECTORY / "aur.list"
    if not path.is_file():
        return []

    entries: list[AurPackage] = []

    for raw in path.read_text(encoding="utf-8").splitlines():
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue

        name, _, comment = stripped.partition("#")
        name = name.strip()
        if name:
            entries.append(AurPackage(name=name, note=comment.strip()))

    return entries


def supported(kind: str) -> list[str]:
    """Names lib/provider.sh declares for a swappable component.

    ``kind`` is one of bootloaders, compositors, shells.
    """
    text = PROVIDER_MODULE.read_text(encoding="utf-8")
    return _read_bash_array(text, f"SUPPORTED_{kind.upper()}")
