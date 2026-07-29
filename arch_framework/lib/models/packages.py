"""Package group selection.

Group names match the ``packages/*.list`` files carried over from the Bash tree,
so the lists stay a plain one-package-per-line format that is easy to review in
a diff.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class PackageGroup(StrEnum):
    BASE = "base"
    FIRMWARE = "firmware"
    FRAMEWORK = "framework"
    DESKTOP = "desktop"
    HYPRLAND = "hyprland"
    FONTS = "fonts"
    MULTIMEDIA = "multimedia"
    DEVELOPMENT = "development"
    OPTIONAL = "optional"


#: Groups without which the result would not be a working machine.
MANDATORY_GROUPS: tuple[PackageGroup, ...] = (
    PackageGroup.BASE,
    PackageGroup.FIRMWARE,
    PackageGroup.FRAMEWORK,
)


class PackageConfig(BaseModel):
    groups: list[PackageGroup] = Field(
        default_factory=lambda: list(MANDATORY_GROUPS)
    )
    #: Anything not worth a group of its own.
    additional: list[str] = Field(default_factory=list)

    def model_post_init(self, _context: object) -> None:
        for group in MANDATORY_GROUPS:
            if group not in self.groups:
                self.groups.insert(0, group)
