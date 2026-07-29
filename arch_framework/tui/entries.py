"""The menu entries.

Shape follows archinstall's global menu — one line per setting, current value
inline, mandatory entries marked, actions at the end — but the set is narrower
on purpose. Mirrors, profiles, network configuration and pacman tuning are
absent because this project has already decided them; asking would imply they
are open questions.

Entries are data. The renderers walk this list and neither knows what any
particular setting means.
"""

from __future__ import annotations

from typing import Any

from ..lib.disk import DeviceHandler
from ..lib.models import PackageGroup
from ..lib.models.device import SafetyStatus
from ..lib.models.packages import MANDATORY_GROUPS
from .draft import Draft
from .menu import NOT_SET, MenuEntry, MenuRegistry
from .prompt import Choice, ask_bool, ask_choice, ask_multi, ask_size, ask_text

#: Console keymaps and their X11/Wayland equivalents. The two naming schemes
#: differ, and getting one right while leaving the other wrong is a classic way
#: to end up with a keyboard that works in the TTY and not in the desktop.
KEYBOARD_LAYOUTS: tuple[tuple[str, str, str, str], ...] = (
    ("fr_CH", "ch", "fr_nodeadkeys", "Swiss French"),
    ("de_CH-latin1", "ch", "de_nodeadkeys", "Swiss German"),
    ("us", "us", "", "US English"),
    ("uk", "gb", "", "British English"),
    ("fr", "fr", "", "French (AZERTY)"),
    ("de-latin1", "de", "nodeadkeys", "German"),
)

TIMEZONES: tuple[str, ...] = (
    "Europe/Zurich",
    "Europe/Paris",
    "Europe/Berlin",
    "Europe/London",
    "UTC",
)

LOCALES: tuple[str, ...] = (
    "en_US.UTF-8",
    "en_GB.UTF-8",
    "fr_CH.UTF-8",
    "de_CH.UTF-8",
    "fr_FR.UTF-8",
)

KERNELS: tuple[tuple[str, str], ...] = (
    ("linux-lts", "Long-term support. Fewer surprises after an update."),
    ("linux", "Latest stable. Newest hardware support."),
    ("linux-zen", "Desktop-tuned scheduling."),
    ("linux-hardened", "Security-focused patches; some hardware misbehaves."),
)

PACKAGE_GROUP_DETAIL: dict[PackageGroup, str] = {
    PackageGroup.BASE: "base, linux firmware, networking, editor. Required.",
    PackageGroup.FIRMWARE: "CPU microcode and device firmware. Required.",
    PackageGroup.FRAMEWORK: "Framework-specific firmware and power tuning. Required.",
    PackageGroup.DESKTOP: "Wayland session, portals, audio.",
    PackageGroup.HYPRLAND: "Hyprland compositor and its immediate tools.",
    PackageGroup.FONTS: "Text and monospace fonts, emoji.",
    PackageGroup.MULTIMEDIA: "Codecs, players, image tools.",
    PackageGroup.DEVELOPMENT: "Toolchains, language runtimes, containers.",
    PackageGroup.OPTIONAL: "Everything else worth having but not needed to boot.",
}


#: Entry keys, in menu order. Declared rather than derived so a saved
#: configuration can be marked fully answered without building the menu first.
#: build_registry asserts it matches what it produces.
ENTRY_KEYS: tuple[str, ...] = (
    "locale",
    "timezone",
    "disk",
    "encryption",
    "swap",
    "kernels",
    "hostname",
    "users",
    "packages",
    "bootloader",
)


def _disk_choices(handler: DeviceHandler) -> list[Choice]:
    """Every disk, with the unusable ones shown and explained.

    Rejected disks are listed rather than hidden: someone who expects to see a
    disk and does not is left guessing, whereas "Rejected: Arch live medium"
    answers the question before it is asked.
    """
    choices: list[Choice] = []
    for path in handler.disks():
        info = handler.info(path)
        verdict = handler.safety(path)
        size = info.size.human() if info and info.size else "unknown size"
        model = info.model if info else "Unknown"

        if verdict.status is SafetyStatus.ELIGIBLE:
            detail = f"{size}, {model}"
        else:
            detail = f"{size}, {model} — {verdict.status.value}: {verdict.reason}"

        choices.append(
            Choice(
                value=path,
                label=path,
                detail=detail,
                enabled=verdict.writable,
            )
        )
    return choices


def build_registry(draft: Draft, handler: DeviceHandler) -> MenuRegistry:
    registry = MenuRegistry()

    # -- locale -------------------------------------------------------------

    def edit_locale(draft: Draft) -> None:
        primary = ask_choice(
            "System locale",
            [Choice(value=name, label=name) for name in LOCALES],
            draft.config.locale.locale,
        )
        layout = ask_choice(
            "Keyboard layout",
            [
                Choice(value=entry, label=entry[3], detail=f"console {entry[0]}, xkb {entry[1]}")
                for entry in KEYBOARD_LAYOUTS
            ],
            next(
                (
                    entry
                    for entry in KEYBOARD_LAYOUTS
                    if entry[0] == draft.config.locale.keymap
                ),
                None,
            ),
        )
        keymap, xkb_layout, xkb_variant, _ = layout  # type: ignore[misc]

        def mutate(payload: dict[str, Any]) -> None:
            payload["locale"]["locale"] = primary
            payload["locale"]["keymap"] = keymap
            payload["locale"]["xkb_layout"] = xkb_layout
            payload["locale"]["xkb_variant"] = xkb_variant

        draft.update(mutate)
        draft.mark_answered("locale")

    registry.add(
        MenuEntry(
            key="locale",
            label="Locale and keyboard",
            preview=lambda d: f"{d.config.locale.locale}, {d.config.locale.keymap}",
            edit=edit_locale,
            help_text=(
                "The console keymap and the graphical layout use different "
                "naming schemes; both are set together so they cannot disagree."
            ),
        )
    )

    # -- timezone -----------------------------------------------------------

    def edit_timezone(draft: Draft) -> None:
        zone = ask_choice(
            "Timezone",
            [Choice(value=name, label=name) for name in TIMEZONES],
            draft.config.locale.timezone,
        )
        ntp = ask_bool("Synchronise the clock over the network", draft.config.locale.ntp)

        def mutate(payload: dict[str, Any]) -> None:
            payload["locale"]["timezone"] = zone
            payload["locale"]["ntp"] = ntp

        draft.update(mutate)
        draft.mark_answered("timezone")

    registry.add(
        MenuEntry(
            key="timezone",
            label="Timezone and clock",
            preview=lambda d: (
                f"{d.config.locale.timezone}"
                f"{', NTP' if d.config.locale.ntp else ', no NTP'}"
            ),
            edit=edit_timezone,
        )
    )

    # -- disk ---------------------------------------------------------------

    def edit_disk(draft: Draft) -> None:
        choices = _disk_choices(handler)
        if not choices:
            raise ValueError(
                "no disks were detected; run on the live ISO, or pass "
                "--devices-from to work from a recording"
            )

        target = ask_choice(
            "Target disk",
            choices,
            draft.config.disk.target_disk,
            help_text=(
                "Everything on the chosen disk is destroyed. Disks that cannot "
                "be used are listed with the reason."
            ),
        )
        efi = ask_size("EFI partition size", draft.config.disk.efi_size)

        def mutate(payload: dict[str, Any]) -> None:
            payload["disk"]["target_disk"] = target
            payload["disk"]["efi_size"] = str(efi)

        draft.update(mutate)
        draft.mark_answered("disk")

        info = handler.info(str(target))
        if info is not None and info.size is not None:
            draft.config.validate_capacity(info.size)

    registry.add(
        MenuEntry(
            key="disk",
            label="Disk configuration",
            # Unanswered until chosen: the profile's placeholder keeps the
            # document valid but is not a decision, and must never be installed
            # onto by default.
            preview=lambda d: (
                f"{d.config.disk.target_disk}, {d.config.disk.efi_size} EFI"
                if d.is_answered("disk")
                else NOT_SET
            ),
            edit=edit_disk,
            mandatory=True,
            help_text="The disk to install onto. Its contents are destroyed.",
        )
    )

    # -- encryption ---------------------------------------------------------

    def edit_encryption(draft: Draft) -> None:
        enabled = ask_bool("Encrypt the system partition", draft.config.encryption.enabled)
        tpm2 = False
        if enabled:
            tpm2 = ask_bool(
                "Unlock automatically with the TPM2",
                draft.config.encryption.tpm2_enabled,
                help_text=(
                    "The TPM releases the key only while firmware and Secure "
                    "Boot state are unchanged. A firmware update can therefore "
                    "stop it working, so a recovery key is always generated and "
                    "shown to you before enrolment."
                ),
            )

        def mutate(payload: dict[str, Any]) -> None:
            payload["encryption"]["enabled"] = enabled
            payload["encryption"]["tpm2_enabled"] = tpm2
            payload["encryption"]["recovery_key"] = True

        draft.update(mutate)
        draft.mark_answered("encryption")

    registry.add(
        MenuEntry(
            key="encryption",
            label="Encryption",
            preview=lambda d: (
                "off"
                if not d.config.encryption.enabled
                else f"LUKS2{' + TPM2' if d.config.encryption.tpm2_enabled else ''}"
            ),
            edit=edit_encryption,
        )
    )

    # -- swap ---------------------------------------------------------------

    def edit_swap(draft: Draft) -> None:
        size = ask_size(
            "Swapfile size",
            draft.config.swap.size,
            help_text=(
                "For hibernation the swapfile must be at least as large as RAM."
            ),
        )
        zram = ask_bool("Enable zram", draft.config.swap.zram_enabled)
        hibernate = ask_bool("Enable hibernation", draft.config.swap.hibernation_enabled)

        def mutate(payload: dict[str, Any]) -> None:
            payload["swap"]["size"] = str(size)
            payload["swap"]["zram_enabled"] = zram

        draft.update(mutate)
        note = draft.set_hibernation(hibernate)
        if note:
            print(f"  {note}")
        draft.mark_answered("swap")

    registry.add(
        MenuEntry(
            key="swap",
            label="Swap and hibernation",
            preview=lambda d: (
                f"{d.config.swap.size}"
                f"{', zram' if d.config.swap.zram_enabled else ''}"
                f"{', hibernation' if d.config.swap.hibernation_enabled else ''}"
            ),
            edit=edit_swap,
        )
    )

    # -- kernels ------------------------------------------------------------

    def edit_kernels(draft: Draft) -> None:
        chosen = ask_multi(
            "Kernels",
            [Choice(value=name, label=name, detail=detail) for name, detail in KERNELS],
            draft.config.system.kernels,
            minimum=1,
            help_text=(
                "The first selection becomes the default boot entry; a second "
                "one is kept as a fallback for when an update goes wrong."
            ),
        )

        def mutate(payload: dict[str, Any]) -> None:
            payload["system"]["default_kernel"] = chosen[0]
            payload["system"]["fallback_kernel"] = chosen[1] if len(chosen) > 1 else None

        draft.update(mutate)
        draft.mark_answered("kernels")

    registry.add(
        MenuEntry(
            key="kernels",
            label="Kernels",
            preview=lambda d: ", ".join(d.config.system.kernels),
            edit=edit_kernels,
            mandatory=True,
        )
    )

    # -- hostname -----------------------------------------------------------

    def edit_hostname(draft: Draft) -> None:
        name = ask_text("Hostname", draft.config.system.hostname)

        def mutate(payload: dict[str, Any]) -> None:
            payload["system"]["hostname"] = name

        draft.update(mutate)
        draft.mark_answered("hostname")

    registry.add(
        MenuEntry(
            key="hostname",
            label="Hostname",
            preview=lambda d: d.config.system.hostname,
            edit=edit_hostname,
            help_text="Lowercase letters, digits and hyphens.",
        )
    )

    # -- users --------------------------------------------------------------

    def edit_users(draft: Draft) -> None:
        name = ask_text(
            "Username",
            draft.config.users.users[0].name if draft.config.users.users else "",
        )
        if not name:
            raise ValueError("a username is required")

        sudo = ask_bool("Grant administrative rights through sudo", True)
        shell = ask_text(
            "Login shell",
            draft.config.users.users[0].shell if draft.config.users.users else "/usr/bin/fish",
        )

        def mutate(payload: dict[str, Any]) -> None:
            payload["users"]["users"] = [
                {"name": name, "sudo": sudo, "shell": shell, "groups": []}
            ]
            # With a sudo user in place, leaving root loginable adds a second
            # password to protect for no gain.
            payload["users"]["root_login_enabled"] = not sudo

        draft.update(mutate)
        draft.mark_answered("users")

    registry.add(
        MenuEntry(
            key="users",
            label="User account",
            preview=lambda d: (
                ", ".join(
                    f"{user.name}{' (sudo)' if user.sudo else ''}"
                    for user in d.config.users.users
                )
                or NOT_SET
            ),
            edit=edit_users,
            mandatory=True,
            help_text=(
                "Passwords are asked for at install time and written to a "
                "separate credentials file, never into the saved configuration."
            ),
        )
    )

    # -- packages -----------------------------------------------------------

    def edit_packages(draft: Draft) -> None:
        chosen = ask_multi(
            "Package groups",
            [
                Choice(
                    value=group.value,
                    label=group.value,
                    detail=PACKAGE_GROUP_DETAIL.get(group, ""),
                )
                for group in PackageGroup
            ],
            [group.value for group in draft.config.packages.groups],
            locked=[group.value for group in MANDATORY_GROUPS],
        )

        def mutate(payload: dict[str, Any]) -> None:
            payload["packages"]["groups"] = chosen

        draft.update(mutate)
        draft.mark_answered("packages")

    registry.add(
        MenuEntry(
            key="packages",
            label="Package groups",
            preview=lambda d: ", ".join(group.value for group in d.config.packages.groups),
            edit=edit_packages,
        )
    )

    # -- bootloader ---------------------------------------------------------

    registry.add(
        MenuEntry(
            key="bootloader",
            label="Bootloader",
            preview=lambda d: str(d.config.bootloader),
            # No edit: Limine is the only supported option, and offering a menu
            # with one entry would suggest otherwise.
            edit=None,
            help_text="Limine is the only supported bootloader.",
        )
    )

    # Keeps ENTRY_KEYS honest: a new entry that is not declared there would be
    # silently missing from the answered set of a reloaded configuration.
    assert tuple(entry.key for entry in registry.entries) == ENTRY_KEYS, (
        "ENTRY_KEYS does not match the registry"
    )
    return registry
