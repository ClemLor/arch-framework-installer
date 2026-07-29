"""Which choices rule out which other choices, and why.

The point of stating these as data rather than burying them in the menu code is
that the menu can then *show* them. An option that cannot be selected is
displayed with the reason it cannot, instead of silently disappearing or being
accepted and then rejected by ``validate_config`` several screens later.

Every rule here mirrors a check in ``lib/config.sh`` or ``lib/memory.sh``. The
Bash side stays authoritative — it runs on the live ISO with the real hardware in
front of it — so this is an early, explanatory copy, never the only guard.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .config import Configuration


class Severity(Enum):
    #: The configuration cannot be installed. Blocks Install.
    BLOCKING = auto()
    #: Allowed, but the user should know. Does not block.
    ADVISORY = auto()


@dataclass(frozen=True)
class Violation:
    severity: Severity
    #: Which setting to point at, so the menu can mark the right line.
    field: str
    message: str

    @property
    def blocking(self) -> bool:
        return self.severity is Severity.BLOCKING


@dataclass(frozen=True)
class Rule:
    """One constraint.

    ``applies`` decides whether the rule is relevant to the current state;
    ``satisfied`` decides whether it is met. Splitting them means a rule that
    does not apply is not reported as passing, which matters when the menu wants
    to explain why an option is locked.
    """

    key: str
    field: str
    message: str
    applies: Callable[["Configuration"], bool]
    satisfied: Callable[["Configuration"], bool]
    severity: Severity = Severity.BLOCKING

    def check(self, config: "Configuration") -> Violation | None:
        if not self.applies(config):
            return None
        if self.satisfied(config):
            return None
        return Violation(self.severity, self.field, self.message)


def _hibernating(config: "Configuration") -> bool:
    return config.hibernation_enabled


def _has_swapfile(config: "Configuration") -> bool:
    return config.swap_size.mib > 0


RULES: tuple[Rule, ...] = (
    # -- encryption ------------------------------------------------------------
    Rule(
        key="tpm2-requires-luks",
        field="tpm2_enabled",
        message=(
            "TPM2 unlocking needs a LUKS container to unlock. Enable encryption "
            "first."
        ),
        applies=lambda c: c.tpm2_enabled,
        satisfied=lambda c: c.luks_enabled,
    ),
    # -- hibernation -----------------------------------------------------------
    Rule(
        key="hibernation-requires-swapfile",
        field="swap_size",
        message=(
            "Hibernation writes the contents of memory to persistent storage. "
            "zram is cleared when power is cut, so a swapfile is required."
        ),
        applies=_hibernating,
        satisfied=_has_swapfile,
    ),
    Rule(
        key="hibernation-requires-swap-subvolume",
        field="swap_size",
        message=(
            "A swapfile needs the @swap subvolume: copy-on-write corrupts a "
            "swapfile, and the attribute can only be cleared on an empty "
            "subvolume."
        ),
        applies=_has_swapfile,
        satisfied=lambda c: "@swap" in c.btrfs_subvolumes,
    ),
    Rule(
        key="hibernation-requires-btrfs",
        field="filesystem",
        message="Hibernation is only implemented for the Btrfs layout.",
        applies=_hibernating,
        satisfied=lambda c: c.filesystem == "btrfs",
    ),
    Rule(
        key="swap-at-least-ram",
        field="swap_size",
        message=(
            "A hibernation image is the whole of memory. A swapfile smaller "
            "than installed RAM cannot hold it, and the kernel only discovers "
            "that part way through suspending."
        ),
        applies=lambda c: _hibernating(c) and c.memory_mib > 0,
        satisfied=lambda c: c.swap_size.mib >= c.memory_mib,
    ),
    # -- storage ---------------------------------------------------------------
    Rule(
        key="disk-must-be-chosen",
        field="target_disk",
        message="No target disk has been chosen.",
        applies=lambda c: True,
        satisfied=lambda c: bool(c.target_disk),
    ),
    Rule(
        key="efi-size-bounds",
        field="efi_size",
        message="The EFI partition must be between 512MiB and 4GiB.",
        applies=lambda c: True,
        satisfied=lambda c: 512 <= c.efi_size.mib <= 4096,
    ),
    Rule(
        key="layout-must-fit",
        field="swap_size",
        message=(
            "The EFI partition, the swapfile and a usable root do not fit on "
            "the selected disk."
        ),
        applies=lambda c: c.disk_size_mib > 0,
        satisfied=lambda c: (
            c.disk_size_mib - c.efi_size.mib - c.swap_size.mib >= 20 * 1024
        ),
    ),
    # -- advisory --------------------------------------------------------------
    Rule(
        key="zram-recommended",
        field="zram_enabled",
        message=(
            "Without zram the system pages straight to disk under memory "
            "pressure, which is markedly slower."
        ),
        applies=lambda c: not c.zram_enabled,
        satisfied=lambda c: False,
        severity=Severity.ADVISORY,
    ),
    Rule(
        key="tpm2-recovery",
        field="tpm2_enabled",
        message=(
            "A TPM2 seal breaks when firmware or Secure Boot state changes. "
            "Keep the passphrase: it is the way back in."
        ),
        applies=lambda c: c.tpm2_enabled,
        satisfied=lambda c: False,
        severity=Severity.ADVISORY,
    ),
)


def evaluate(config: "Configuration") -> list[Violation]:
    """Every violation in the current state, blocking ones first."""
    violations = [
        violation for rule in RULES if (violation := rule.check(config)) is not None
    ]
    return sorted(violations, key=lambda v: 0 if v.blocking else 1)


def blocking(config: "Configuration") -> list[Violation]:
    return [violation for violation in evaluate(config) if violation.blocking]


def is_installable(config: "Configuration") -> bool:
    return not blocking(config)


@dataclass
class LockReason:
    """Why a particular candidate value cannot be selected."""

    value: object
    reason: str


@dataclass
class Availability:
    """Which values a setting may take right now.

    Computed by trial: each candidate is applied to a copy of the configuration
    and the rules are re-evaluated. That means a new rule automatically affects
    what the menu offers, with no second place to update.
    """

    allowed: list[object] = field(default_factory=list)
    locked: list[LockReason] = field(default_factory=list)

    def reason_for(self, value: object) -> str | None:
        for entry in self.locked:
            if entry.value == value:
                return entry.reason
        return None


def availability(
    config: "Configuration",
    field_name: str,
    candidates: list[object],
    apply: Callable[["Configuration", object], "Configuration"] | None = None,
) -> Availability:
    """Split candidates into selectable and locked, each with a reason.

    ``apply`` builds the trial state for a candidate. It matters whenever
    choosing a value also adjusts something else: a swap size brings the ``@swap``
    subvolume with it, so trialling the size alone would lock every non-zero
    size for want of a subvolume the menu would have created anyway. Locking a
    choice for a consequence of that same choice is not a constraint, it is a
    bug.
    """
    result = Availability()
    build = apply or (lambda c, value: c.with_value(field_name, value))

    for candidate in candidates:
        trial = build(config, candidate)
        # target_disk is reported by its own entry; a disk not yet chosen must not
        # make every other option look locked.
        violations = [v for v in blocking(trial) if v.field != "target_disk"]

        if violations:
            result.locked.append(LockReason(candidate, violations[0].message))
        else:
            result.allowed.append(candidate)

    return result
