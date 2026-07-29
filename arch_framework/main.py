"""Entry point.

Modes mirror the Bash implementation so existing habits and documentation still
apply: ``--inspect`` and ``--plan-storage`` never touch the system, ``--dry-run``
prints what would be done. ``--tui`` is the new guided configuration.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .lib import log
from .lib.command import CommandRunner, set_runner
from .lib.disk.source import FixtureSource, set_source
from .lib.exceptions import InstallerError
from .lib.hardware import Hardware
from .lib.models import InstallConfig, Size
from .profiles import default_config

DEFAULT_CONFIG_PATH = Path.home() / "framework-install.json"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="arch-framework-installer",
        description="Reproducible Arch Linux installation for Framework laptops.",
    )
    parser.add_argument("--version", action="version", version=__version__)

    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--tui",
        action="store_true",
        help="guided configuration menu",
    )
    mode.add_argument(
        "--inspect",
        action="store_true",
        help="report host and disk facts, then exit",
    )
    mode.add_argument(
        "--plan-storage",
        action="store_true",
        help="validate and print the planned disk layout, then exit",
    )

    parser.add_argument(
        "--config",
        type=Path,
        help=f"configuration to load (default: {DEFAULT_CONFIG_PATH})",
    )
    parser.add_argument(
        "--creds",
        type=Path,
        help="credentials file, kept separate from the configuration",
    )
    parser.add_argument(
        "--renderer",
        choices=("plain", "textual"),
        help="force a menu renderer instead of autodetecting",
    )
    parser.add_argument(
        "--devices-from",
        type=Path,
        metavar="FIXTURE",
        help=(
            "read block devices from a recorded fixture instead of the real "
            "machine; for development and tests only"
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="print the operations that would run, without executing them",
    )
    parser.add_argument("--verbose", action="store_true", help="echo every command")
    return parser


def load_or_default(path: Path | None) -> InstallConfig:
    if path is None:
        return default_config()
    return InstallConfig.load(path)


def inspect(config: InstallConfig) -> int:
    from .lib.disk.source import get_source

    hardware = Hardware()
    host = hardware.info()

    log.section("Host system")
    log.info(f"Environment:       {'Arch live ISO' if host.live_environment else 'other'}")
    log.info(f"Vendor:            {host.vendor}")
    log.info(f"Machine:           {host.machine}")
    log.info(f"CPU:               {host.cpu}")
    log.info(f"Memory:            {host.memory.human() if host.memory else 'Unknown'}")
    log.info(f"Boot mode:         {'UEFI' if host.uefi else 'Legacy BIOS'}")
    log.info(f"Secure Boot:       {host.secure_boot}")
    log.info(f"Firmware:          {host.firmware_vendor} {host.firmware_version}")

    log.section("Block devices")
    devices = get_source().block_devices()
    disks = [device for device in devices if device.get("type") == "disk"]
    if not disks:
        log.warn("No disks reported.")
    for disk in disks:
        name = disk.get("path") or disk.get("name")
        raw_size = disk.get("size")
        size = Size.from_bytes(raw_size).human() if isinstance(raw_size, int) else "Unknown"
        transport = disk.get("tran") or "unknown"
        log.info(
            f"{name:<16} {size:>10}  {transport:<5} {disk.get('model') or 'Unknown'}"
        )

    log.section("Configuration")
    log.info(f"Target disk:       {config.disk.target_disk}")
    log.info(f"Hostname:          {config.system.hostname}")
    log.info(f"Encryption:        {config.encryption.enabled} (TPM2 {config.encryption.tpm2_enabled})")
    log.info(f"Swap:              {config.swap.size} (hibernation {config.swap.hibernation_enabled})")
    log.info(f"Bootloader:        {config.bootloader}")
    log.info(f"Kernels:           {', '.join(config.system.kernels)}")

    if not host.live_environment:
        log.warn("Not the Arch live ISO: inspection only, installation is refused here.")

    log.success("Inspection completed without modifying the system.")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    set_runner(CommandRunner(dry_run=args.dry_run, verbose=args.verbose))

    if args.devices_from is not None:
        set_source(FixtureSource.from_file(args.devices_from))
        log.warn(
            f"reading devices from {args.devices_from}; this is not the real machine"
        )

    try:
        config = load_or_default(args.config)

        if args.inspect:
            return inspect(config)

        if args.plan_storage:
            log.error("--plan-storage is not implemented on this branch yet.")
            return 2

        if args.tui:
            log.error("--tui is not implemented yet; phase 3.")
            return 2

        log.error("No mode selected. Try --tui, --inspect or --help.")
        return 2

    except InstallerError as exc:
        log.error(str(exc))
        return 1
    except KeyboardInterrupt:
        log.warn("Interrupted.")
        return 130
    except EOFError:
        # Reached when a renderer prompts with no interactive stdin, such as a
        # piped or scripted run. A traceback here would read as a crash.
        log.error(
            "No input available. Pass --config to run without prompting, "
            "or run from a terminal."
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
