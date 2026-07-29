"""The menu.

Shape follows archinstall: one line per setting, current value inline, mandatory
entries marked, and Save / Install / Quit at the end.

What it adds is the locking. When a choice becomes incompatible with the current
state, it is still listed — greyed out, with the reason. The alternative, hiding
it, leaves the user wondering where the option went; the other alternative,
accepting it and failing later in ``validate_config``, wastes their time and
teaches them nothing.
"""

from __future__ import annotations

import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum, auto

from . import catalogue, constraints
from .config import Configuration, Size
from .devices import enumerate_disks

NOT_SET = "(not set)"


class Action(Enum):
    SAVE = auto()
    INSTALL = auto()
    QUIT = auto()


@dataclass
class Entry:
    key: str
    label: str
    preview: Callable[[Configuration], str]
    edit: Callable[[Configuration], str | None] | None = None
    mandatory: bool = False
    help_text: str = ""


@dataclass
class Menu:
    entries: list[Entry] = field(default_factory=list)

    def add(self, entry: Entry) -> "Menu":
        self.entries.append(entry)
        return self

    def get(self, key: str) -> Entry | None:
        return next((e for e in self.entries if e.key == key), None)

    def render(self, config: Configuration) -> list[str]:
        width = max(len(entry.label) for entry in self.entries)
        violations = {v.field: v for v in constraints.evaluate(config)}

        lines: list[str] = []
        for number, entry in enumerate(self.entries, start=1):
            marker = "*" if entry.mandatory else " "
            label = f"{entry.label} ".ljust(width + 2, ".")
            line = f"{marker} {number:>2}) {label} {entry.preview(config)}"

            problem = violations.get(entry.key)
            if problem is not None:
                tag = "BLOCKED" if problem.blocking else "note"
                line += f"\n         {tag}: {problem.message}"
            lines.append(line)
        return lines


# ------------------------------------------------------------------------------
# Prompts
# ------------------------------------------------------------------------------


def _read(prompt: str) -> str:
    answer = input(prompt)
    if answer.strip().lower() in {":q", ":quit"}:
        raise _Abandoned
    return answer


class _Abandoned(Exception):
    """The user left a prompt without answering."""


def ask_text(label: str, current: str) -> str:
    answer = _read(f"{label} [{current}]: ").strip()
    return answer or current


def ask_bool(label: str, current: bool) -> bool:
    default = "Y/n" if current else "y/N"
    while True:
        answer = _read(f"{label} [{default}]: ").strip().lower()
        if not answer:
            return current
        if answer in {"y", "yes"}:
            return True
        if answer in {"n", "no"}:
            return False
        print("  Answer y or n.")


def ask_checkboxes(
    label: str,
    options: list[tuple[object, str, str | None]],
    selected: list[object],
    *,
    locked_on: list[object] = (),
) -> list[object]:
    """Toggle any number of options, archinstall-style.

    Each option is ``(value, description, unavailable_reason)``. ``locked_on``
    values are always selected and cannot be turned off — used for the package
    groups the machine would not boot without, which are better shown as
    permanently ticked than hidden.
    """
    chosen = {
        value for value, _, reason in options if value in selected and not reason
    }
    chosen.update(locked_on)

    print(f"\n{label}")
    while True:
        for number, (value, description, reason) in enumerate(options, start=1):
            if reason:
                mark = "-"
            elif value in chosen:
                mark = "x"
            else:
                mark = " "

            suffix = ""
            if value in locked_on:
                suffix = "  (always installed)"
            print(f"  {number:>2}) [{mark}] {description}{suffix}")
            if reason:
                print(f"          unavailable: {reason}")

        print("   a) select all    n) select none    Enter) accept")
        answer = _read("Toggle: ").strip().lower()

        if not answer:
            return [value for value, _, _ in options if value in chosen]

        if answer == "a":
            chosen = {
                value for value, _, reason in options if not reason
            } | set(locked_on)
            continue
        if answer == "n":
            chosen = set(locked_on)
            continue

        if not answer.isdigit():
            print("  Enter a number, a, n, or Enter.")
            continue

        index = int(answer) - 1
        if index not in range(len(options)):
            print("  Out of range.")
            continue

        value, description, reason = options[index]
        if reason:
            print(f"  Not available: {reason}")
            continue
        if value in locked_on:
            print(f"  {description} cannot be removed.")
            continue

        chosen.symmetric_difference_update({value})


def ask_locked_choice(
    label: str,
    options: list[tuple[object, str, str | None]],
    current: object,
) -> object:
    """Choose from options, some of which may be locked.

    Each option is ``(value, description, lock_reason)``. A locked option is
    shown and refuses selection with its reason, rather than being hidden.
    """
    print(f"\n{label}")
    for number, (value, description, lock) in enumerate(options, start=1):
        mark = "x" if value == current else " "
        if lock:
            print(f"  {number:>2}) [-] {description}")
            print(f"          locked: {lock}")
        else:
            print(f"  {number:>2}) [{mark}] {description}")

    while True:
        answer = _read("Choose (Enter to keep): ").strip()
        if not answer:
            return current
        if not answer.isdigit():
            print("  Enter a number.")
            continue

        index = int(answer) - 1
        if index not in range(len(options)):
            print("  Out of range.")
            continue

        value, _, lock = options[index]
        if lock:
            print(f"  Not available: {lock}")
            continue
        return value


# ------------------------------------------------------------------------------
# Entries
# ------------------------------------------------------------------------------

# Console keymap, xkb layout, xkb variant, label.
#
# Kept as one table because the console and graphical names differ and getting
# one right while leaving the other wrong is the classic way to end up with a
# keyboard that works in the TTY and not in the desktop.
KEYBOARD_LAYOUTS: list[tuple[str, str, str, str]] = [
    ("fr_CH", "ch", "fr_nodeadkeys", "Swiss French"),
    ("de_CH-latin1", "ch", "de_nodeadkeys", "Swiss German"),
    ("fr", "fr", "", "French (AZERTY)"),
    ("de-latin1", "de", "nodeadkeys", "German"),
    ("uk", "gb", "", "British English"),
    ("us", "us", "", "US English"),
]

SWAP_CHOICES = [Size(0), Size(8 * 1024), Size(16 * 1024), Size(32 * 1024), Size(64 * 1024)]
EFI_CHOICES = [Size(512), Size(1024), Size(2048), Size(4096)]
KERNELS = ["linux-lts", "linux", "linux-zen", "linux-hardened"]


def _swap_options(config: Configuration) -> list[tuple[object, str, str | None]]:
    """Swap sizes, with the ones incompatible with the current state locked.

    Trialled through ``with_swap_size`` rather than a bare field change, so each
    candidate is judged together with the @swap subvolume that selecting it would
    create. Judging the size alone would lock every non-zero size for want of a
    subvolume the menu adds as part of the same action.
    """
    available = constraints.availability(
        config,
        "swap_size",
        list(SWAP_CHOICES),
        apply=lambda c, value: c.with_swap_size(value),  # type: ignore[arg-type]
    )
    options: list[tuple[object, str, str | None]] = []
    for size in SWAP_CHOICES:
        if size.mib == 0:
            description = "no swapfile (zram only)"
        elif config.memory_mib and size.mib >= config.memory_mib:
            description = f"{size.human()} (enough for hibernation)"
        else:
            description = size.human()
        options.append((size, description, available.reason_for(size)))
    return options


def build_menu() -> Menu:
    menu = Menu()

    def edit_disk(config: Configuration) -> str | None:
        disks = enumerate_disks()
        if not disks:
            raise ValueError(
                "no disks detected; run on the live ISO, or set "
                "AFI_DEVICES_FIXTURE to a recorded capture"
            )

        options = [
            (disk.path, f"{disk.path}  {disk.describe()}", disk.rejection)
            for disk in disks
        ]
        chosen = ask_locked_choice("Target disk", options, config.target_disk)
        config.target_disk = str(chosen)
        config.answered.add("target_disk")

        selected = next((d for d in disks if d.path == chosen), None)
        if selected is not None:
            config.disk_size_mib = selected.size_mib
        return None

    menu.add(
        Entry(
            key="target_disk",
            label="Target disk",
            preview=lambda c: (
                c.target_disk if "target_disk" in c.answered else NOT_SET
            ),
            edit=edit_disk,
            mandatory=True,
            help_text="Everything on the chosen disk is destroyed.",
        )
    )

    def edit_efi(config: Configuration) -> str | None:
        available = constraints.availability(config, "efi_size", list(EFI_CHOICES))
        options = [
            (size, size.human(), available.reason_for(size)) for size in EFI_CHOICES
        ]
        config.efi_size = ask_locked_choice("EFI size", options, config.efi_size)
        return None

    menu.add(
        Entry(
            key="efi_size",
            label="EFI partition",
            preview=lambda c: c.efi_size.human(),
            edit=edit_efi,
        )
    )

    def edit_encryption(config: Configuration) -> str | None:
        enabled = ask_bool("Encrypt the system partition (LUKS2)", config.luks_enabled)
        note = config.set_encryption(enabled)

        if config.luks_enabled:
            available = constraints.availability(config, "tpm2_enabled", [True, False])
            options = [
                (True, "unlock automatically with the TPM2", available.reason_for(True)),
                (False, "always ask for the passphrase", available.reason_for(False)),
            ]
            config.tpm2_enabled = bool(
                ask_locked_choice("TPM2 unlocking", options, config.tpm2_enabled)
            )
        return note

    menu.add(
        Entry(
            key="tpm2_enabled",
            label="Encryption",
            preview=lambda c: (
                "off"
                if not c.luks_enabled
                else f"LUKS2{' + TPM2' if c.tpm2_enabled else ''}"
            ),
            edit=edit_encryption,
            help_text=(
                "A TPM2 seal is bound to firmware state; the passphrase remains "
                "the way in when it breaks."
            ),
        )
    )

    def edit_memory(config: Configuration) -> str | None:
        notes: list[str] = []

        config.zram_enabled = ask_bool(
            "Enable zram (compressed swap in RAM)", config.zram_enabled
        )

        hibernate = ask_bool("Enable hibernation", config.hibernation_enabled)
        note = config.set_hibernation(hibernate)
        if note:
            notes.append(note)

        # Asked after the toggle so the locking reflects the choice just made:
        # with hibernation on, "no swapfile" and any size below RAM are locked.
        chosen = ask_locked_choice(
            "Swapfile size", _swap_options(config), config.swap_size
        )
        note = config.apply_swap_size(chosen)  # type: ignore[arg-type]
        if note:
            notes.append(note)

        return "; ".join(notes) if notes else None

    menu.add(
        Entry(
            key="swap_size",
            label="Memory and hibernation",
            preview=lambda c: ", ".join(
                filter(
                    None,
                    [
                        "zram" if c.zram_enabled else None,
                        f"swap {c.swap_size.human()}" if c.swap_size.mib else None,
                        "hibernation" if c.hibernation_enabled else None,
                    ],
                )
            )
            or "none",
            edit=edit_memory,
            help_text=(
                "zram handles everyday pressure. Hibernation additionally needs a "
                "swapfile at least the size of RAM, on a no-copy-on-write "
                "subvolume."
            ),
        )
    )

    def edit_kernels(config: Configuration) -> str | None:
        options = [(name, name, None) for name in KERNELS]
        config.default_kernel = str(
            ask_locked_choice("Default kernel", options, config.default_kernel)
        )
        fallback = [(name, name, None) for name in KERNELS if name != config.default_kernel]
        fallback.append((None, "no fallback entry", None))
        chosen = ask_locked_choice("Fallback kernel", fallback, config.fallback_kernel)
        config.fallback_kernel = str(chosen) if chosen else ""
        return None

    menu.add(
        Entry(
            key="default_kernel",
            label="Kernels",
            preview=lambda c: ", ".join(filter(None, [c.default_kernel, c.fallback_kernel])),
            edit=edit_kernels,
        )
    )

    def edit_identity(config: Configuration) -> str | None:
        config.hostname = ask_text("Hostname", config.hostname)
        config.username = ask_text("Username", config.username)
        config.user_shell = ask_text("Login shell", config.user_shell)
        config.answered.add("username")
        return None

    menu.add(
        Entry(
            key="username",
            label="Hostname and user",
            preview=lambda c: f"{c.hostname} / {c.username}",
            edit=edit_identity,
            mandatory=True,
        )
    )

    def edit_locale(config: Configuration) -> str | None:
        config.locale = ask_text("Locale", config.locale)
        config.secondary_locale = ask_text(
            "Secondary locale", config.secondary_locale
        )

        # One choice sets the console keymap and the graphical layout together.
        # They use different naming schemes, and setting only the keymap leaves
        # the desktop on US QWERTY while the console is correct — a failure that
        # does not look like a keyboard configuration problem.
        current = next(
            (entry for entry in KEYBOARD_LAYOUTS if entry[0] == config.keymap), None
        )
        chosen = ask_locked_choice(
            "Keyboard",
            [
                (entry, f"{entry[3]}  (console {entry[0]}, xkb {entry[1]})", None)
                for entry in KEYBOARD_LAYOUTS
            ],
            current,
        )
        if chosen is not None:
            keymap, xkb_layout, xkb_variant, _ = chosen  # type: ignore[misc]
            config.keymap = keymap
            config.xkb_layout = xkb_layout
            config.xkb_variant = xkb_variant

        config.timezone = ask_text("Timezone", config.timezone)
        return None

    menu.add(
        Entry(
            key="locale",
            label="Locale and keyboard",
            preview=lambda c: (
                f"{c.locale}, {c.keymap}"
                f"{'/' + c.xkb_variant if c.xkb_variant else ''}, {c.timezone}"
            ),
            edit=edit_locale,
            help_text=(
                "The console keymap and the graphical layout use different naming "
                "schemes; both are set from one choice so they cannot disagree."
            ),
        )
    )

    def edit_desktop(config: Configuration) -> str | None:
        # Offered from the names lib/provider.sh declares, so adding a compositor
        # makes it appear here without this file changing.
        compositors = catalogue.supported("compositors")
        if len(compositors) > 1:
            config.desktop_compositor = str(
                ask_locked_choice(
                    "Compositor",
                    [(name, name, None) for name in compositors],
                    config.desktop_compositor,
                )
            )

        config.desktop_autologin = ask_bool(
            f"Log in automatically to the {config.desktop_compositor} session",
            config.desktop_autologin,
        )
        return None

    menu.add(
        Entry(
            key="desktop_autologin",
            label="Desktop session",
            preview=lambda c: (
                f"{c.desktop_compositor}"
                f"{' + ' + c.desktop_shell if c.desktop_shell else ''}"
                f"{', autologin' if c.desktop_autologin else ''}"
            ),
            edit=edit_desktop,
            help_text=(
                "Only implemented sessions are offered. Adding one means adding "
                "desktop_<name>_* functions in lib/ and listing the name."
            ),
        )
    )

    def edit_bootloader(config: Configuration) -> str | None:
        bootloaders = catalogue.supported("bootloaders")
        if len(bootloaders) <= 1:
            raise ValueError(
                f"{bootloaders[0] if bootloaders else 'none'} is the only "
                "implemented bootloader; there is nothing to choose"
            )
        config.bootloader = str(
            ask_locked_choice(
                "Bootloader",
                [(name, name, None) for name in bootloaders],
                config.bootloader,
            )
        )
        return None

    menu.add(
        Entry(
            key="bootloader",
            label="Bootloader",
            preview=lambda c: c.bootloader,
            edit=edit_bootloader,
            help_text=(
                "Chosen by name and dispatched, so adding one means adding "
                "bootloader_<name>_* functions and listing the name."
            ),
        )
    )

    # -- software selection ---------------------------------------------------

    def edit_groups(config: Configuration) -> str | None:
        groups = catalogue.package_groups()
        mandatory = [group.name for group in groups if group.mandatory]

        # Nothing selected yet means everything, which is what the shell does
        # with an unset PACKAGE_GROUPS.
        current = config.package_groups or [group.name for group in groups]

        chosen = ask_checkboxes(
            "Package groups",
            [(group.name, group.description, None) for group in groups],
            current,
            locked_on=mandatory,
        )

        # Recorded as "all" rather than an explicit list when nothing was
        # deselected, so the generated file stays quiet about defaults.
        if len(chosen) == len(groups):
            config.package_groups = []
            return "every group selected"

        config.package_groups = [str(name) for name in chosen]
        skipped = [g.name for g in groups if g.name not in chosen]
        return f"skipping: {', '.join(skipped)}"

    menu.add(
        Entry(
            key="package_groups",
            label="Package groups",
            preview=lambda c: (
                "all" if not c.package_groups else ", ".join(c.package_groups)
            ),
            edit=edit_groups,
            help_text=(
                "base, firmware and framework cannot be deselected: without them "
                "the result does not boot or cannot be repaired."
            ),
        )
    )

    def edit_aur(config: Configuration) -> str | None:
        packages = catalogue.aur_packages()
        if not packages:
            raise ValueError("packages/aur.list is empty; nothing to choose")

        current = (
            config.aur_packages
            if config.aur_selected
            else [package.name for package in packages]
        )

        chosen = ask_checkboxes(
            "AUR software (installed after the first boot)",
            [(package.name, package.description, None) for package in packages],
            current,
        )

        config.aur_packages = [str(name) for name in chosen]
        config.aur_selected = True

        if not chosen:
            return "no AUR software; afi-aur-setup is still installed for later"
        return f"{len(chosen)} package(s) selected"

    menu.add(
        Entry(
            key="aur_packages",
            label="AUR software",
            preview=lambda c: (
                "all" if not c.aur_selected
                else (", ".join(c.aur_packages) if c.aur_packages else "none")
            ),
            edit=edit_aur,
            help_text=(
                "Built after the first boot by afi-aur-setup, never during the "
                "installation: a broken PKGBUILD must not be able to fail an "
                "install that would otherwise boot."
            ),
        )
    )

    return menu


# ------------------------------------------------------------------------------
# Loop
# ------------------------------------------------------------------------------


def run(menu: Menu, config: Configuration) -> Action:
    while True:
        print("\nArch Framework Installer — configuration\n")
        for line in menu.render(config):
            print(line)

        problems = constraints.blocking(config)
        unanswered = [
            entry.label
            for entry in menu.entries
            if entry.mandatory and entry.preview(config) == NOT_SET
        ]

        print()
        if problems:
            print(f"  {len(problems)} blocking problem(s) above.")
        if unanswered:
            print(f"  Unanswered and required: {', '.join(unanswered)}")
        print("\n   s) Save    i) Install    q) Quit      * = required\n")

        try:
            choice = _read("> ").strip().lower()
        except _Abandoned:
            return Action.QUIT

        if choice in {"q", "quit"}:
            return Action.QUIT
        if choice in {"s", "save"}:
            return Action.SAVE
        if choice in {"i", "install"}:
            if problems or unanswered:
                print("\nCannot install until the problems above are resolved.\n")
                continue
            return Action.INSTALL

        entry = None
        if choice.isdigit():
            index = int(choice) - 1
            if 0 <= index < len(menu.entries):
                entry = menu.entries[index]
        else:
            entry = menu.get(choice)

        if entry is None:
            print("\nUnrecognised choice.\n")
            continue
        if entry.edit is None:
            print(f"\n{entry.label} is not editable.\n")
            continue

        if entry.help_text:
            print(f"\n{entry.help_text}")
        try:
            note = entry.edit(config)
        except _Abandoned:
            print("\nLeft unchanged.\n")
        except ValueError as exc:
            print(f"\nRejected: {exc}\n")
        else:
            if note:
                print(f"\n  {note}\n")


def stdin_is_interactive() -> bool:
    return sys.stdin.isatty()
