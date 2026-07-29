"""The guided configuration flow.

Equivalent to archinstall's guided installer: walk the menu, then save, install
or abort. Saving is not a lesser outcome — a saved configuration replayed with
``--config`` is what makes a rebuild reproducible, and is the point of the whole
project.
"""

from __future__ import annotations

import sys
from pathlib import Path

from ..lib import log
from ..lib.disk import DeviceHandler
from ..lib.exceptions import InstallerError
from ..lib.hardware import Hardware
from ..lib.models import InstallConfig
from ..tui import Action, select_renderer
from ..tui.draft import Draft
from ..tui.entries import ENTRY_KEYS, build_registry


def report_environment(hardware: Hardware) -> None:
    host = hardware.info()
    log.section("Detected machine")
    log.info(f"{host.vendor} {host.machine}")
    log.info(f"CPU: {host.cpu}")
    log.info(f"Memory: {host.memory.human() if host.memory else 'Unknown'}")
    log.info(f"Boot mode: {'UEFI' if host.uefi else 'Legacy BIOS'}")
    log.info(f"Secure Boot: {host.secure_boot}")

    if not host.is_framework:
        log.warn(
            "This does not look like a Framework laptop. The defaults are tuned "
            "for one; review every entry before installing."
        )
    if not host.uefi:
        log.warn("Not booted in UEFI mode. This installer requires UEFI.")
    if not host.live_environment:
        log.warn(
            "Not running from the Arch live ISO. The menu works, but installing "
            "is refused outside the live environment."
        )


def check_against_hardware(config: InstallConfig, hardware: Hardware) -> None:
    """Warn about a configuration the machine cannot honour.

    Warnings, not refusals: the configuration may be being written for a
    different machine than the one running the menu.
    """
    handler = DeviceHandler()

    verdict = handler.safety(config.disk.target_disk)
    if not verdict.writable:
        log.warn(f"Target disk {config.disk.target_disk} is not writable — {verdict}")

    info = handler.info(config.disk.target_disk)
    if info is not None and info.size is not None:
        try:
            config.validate_capacity(info.size)
        except InstallerError as exc:
            log.warn(str(exc))

    memory = hardware.info().memory
    if memory is not None:
        try:
            config.validate_hibernation(memory.bytes)
        except InstallerError as exc:
            log.warn(str(exc))


def summarise(config: InstallConfig) -> None:
    log.section("Configuration")
    log.info(f"Hostname:     {config.system.hostname}")
    log.info(f"Target disk:  {config.disk.target_disk}")
    log.info(f"EFI:          {config.disk.efi_size}")
    log.info(
        f"Encryption:   "
        f"{'LUKS2' if config.encryption.enabled else 'none'}"
        f"{' + TPM2' if config.encryption.tpm2_enabled else ''}"
    )
    log.info(f"Subvolumes:   {' '.join(config.disk.subvolumes)}")
    log.info(
        f"Swap:         {config.swap.size}"
        f"{', hibernation' if config.swap.hibernation_enabled else ''}"
    )
    log.info(f"Kernels:      {', '.join(config.system.kernels)}")
    log.info(f"Packages:     {', '.join(g.value for g in config.packages.groups)}")
    log.info(
        f"Users:        "
        f"{', '.join(user.name for user in config.users.users) or 'none'}"
    )
    log.info(f"Bootloader:   {config.bootloader}")

    aur = config.bootloader.aur_packages
    if aur:
        log.info(
            f"After first boot, install from the AUR: {', '.join(aur)} "
            "(not available during installation)"
        )


def run(
    config: InstallConfig,
    *,
    config_path: Path,
    renderer_name: str | None = None,
    from_saved: bool = False,
    creds_path: Path | None = None,
) -> int:
    hardware = Hardware()
    report_environment(hardware)

    handler = DeviceHandler()

    # Provenance decides what counts as answered. A configuration loaded from a
    # file records decisions already made; one built from the profile carries a
    # placeholder disk that nobody chose.
    if from_saved:
        draft = Draft.from_saved(config, ENTRY_KEYS)
        log.info(f"Loaded {config_path}. Press i to install it unchanged.")
    else:
        draft = Draft(config)

    registry = build_registry(draft, handler)
    renderer = select_renderer(registry, prefer=renderer_name)
    log.info(f"Menu renderer: {renderer.name}")

    action = renderer.run(draft)

    if action is Action.ABORT:
        log.warn("Aborted. Nothing was written.")
        return 130

    summarise(draft.config)
    check_against_hardware(draft.config, hardware)

    if action is Action.SAVE:
        draft.config.save(config_path)
        log.success(f"Configuration saved to {config_path}")
        log.info(
            "Replay it with: arch-framework-installer --config "
            f"{config_path}"
        )
        return 0

    # Action.INSTALL
    # Saved before anything is touched: if the installation fails, the answers
    # are not lost with it.
    draft.config.save(config_path)
    log.success(f"Configuration saved to {config_path}")

    from ..lib.installer import install
    from . import credentials as creds

    interactive = sys.stdin.isatty()
    collected = creds.collect(draft.config, path=creds_path, interactive=interactive)

    verdict = DeviceHandler().safety(draft.config.disk.target_disk)
    log.section("Point of no return")
    log.warn(f"Everything on {draft.config.disk.target_disk} will be destroyed.")
    log.info(f"Safety check: {verdict}")

    if interactive:
        answer = input(f"Type {draft.config.disk.target_disk} to continue: ").strip()
        if answer != draft.config.disk.target_disk:
            log.warn("Not confirmed. Nothing was changed.")
            return 130

    return install(draft.config, collected, interactive=interactive)
