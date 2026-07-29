"""Graphical configuration front-end for the Bash installer.

This does not install anything. It edits configuration, writes
``config/generated.conf`` for ``lib/config.sh`` to source, and then optionally
hands over to ``install.sh``. Keeping the destructive work in one place means
there is a single implementation to trust, and the Bash validation stays
authoritative because it runs on the live ISO with the real hardware present.
"""

from __future__ import annotations

import argparse
import functools
import os
import sys
from collections.abc import Callable
from pathlib import Path

from . import constraints, runner
from .config import Configuration
from .devices import memory_mib
from .menu import Action, Menu, build_menu, run, stdin_is_interactive

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SYSTEM_CONFIG = PROJECT_ROOT / "config" / "system.conf"
GENERATED_CONFIG = PROJECT_ROOT / "config" / "generated.conf"
INSTALLER = PROJECT_ROOT / "install.sh"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="configurator",
        description=(
            "Configure the Arch Framework installer, then optionally run it."
        ),
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=GENERATED_CONFIG,
        help=f"where to write the answers (default: {GENERATED_CONFIG})",
    )
    parser.add_argument(
        "--show",
        action="store_true",
        help="print the current configuration and its problems, then exit",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="pass --dry-run to install.sh when handing over",
    )
    parser.add_argument(
        "--text",
        action="store_true",
        help="use the plain prompts instead of the full-screen interface",
    )
    parser.add_argument(
        "--tui",
        action="store_true",
        help="use the full-screen interface even if the terminal looks unsuitable",
    )
    return parser


def load(path: Path) -> Configuration:
    """Start from the tracked defaults, then apply any previous answers.

    Same layering the shell uses, so what the menu shows is what install.sh will
    see rather than an approximation of it.
    """
    config = Configuration.load(SYSTEM_CONFIG)

    if path.is_file():
        previous = Configuration.load(path)
        config = previous
        # A file that was written by this tool records decisions already made, so
        # its target disk counts as chosen. Requiring the menu to be walked again
        # would defeat replaying a saved configuration.
        if previous.target_disk:
            config.answered.add("target_disk")
        config.answered.add("username")

    config.memory_mib = memory_mib()
    return config


def report(config: Configuration) -> None:
    print("Configuration")
    print(f"  target disk   {config.target_disk or '(not set)'}")
    print(f"  encryption    {'LUKS2' if config.luks_enabled else 'none'}"
          f"{' + TPM2' if config.tpm2_enabled else ''}")
    print(f"  swap          {config.swap_size.human()}")
    print(f"  zram          {'on' if config.zram_enabled else 'off'}")
    print(f"  hibernation   {'on' if config.hibernation_enabled else 'off'}")
    print(f"  subvolumes    {' '.join(config.btrfs_subvolumes)}")
    print(f"  kernels       {config.default_kernel} {config.fallback_kernel}".rstrip())

    violations = constraints.evaluate(config)
    if not violations:
        print("\nNo problems found.")
        return

    print()
    for violation in violations:
        tag = "BLOCKING" if violation.blocking else "note    "
        print(f"  {tag}  {violation.field}: {violation.message}")


def hand_over(config_path: Path, *, dry_run: bool) -> int:
    """Replace this process with install.sh.

    exec rather than a subprocess: the installer is interactive and asks for
    confirmation before destroying anything, and it should own the terminal
    outright rather than inherit it through a wrapper.
    """
    if not INSTALLER.is_file():
        print(f"install.sh not found at {INSTALLER}", file=sys.stderr)
        return 1

    argv = ["bash", str(INSTALLER)]
    if dry_run:
        argv.append("--dry-run")

    print(f"\nHanding over to: {' '.join(argv)}")
    print(f"Answers in: {config_path}\n")

    if os.geteuid() != 0:
        print(
            "install.sh must run as root. Re-run this with sudo, or start it "
            f"yourself:\n  sudo ./install.sh\n",
            file=sys.stderr,
        )
        return 1

    os.execvp(argv[0], argv)


def follow_dry_run(config_path: Path, config: Configuration) -> int:
    """Run install.sh --dry-run and draw its progress on a full screen.

    Only for a dry run. A real installation asks for a passphrase, a typed device
    path and two passwords, which a curses interface cannot answer without
    rewriting the parts of the installer that handle secrets — so it keeps the
    hand-over path instead.
    """
    from . import runner as runner_module
    from . import tui

    # No --config: that flag replaces config/system.conf, while the answers are an
    # overlay the installer sources by itself. hand_over does the same, and for the
    # same reason.
    if config_path != GENERATED_CONFIG:
        print(
            f"Note: install.sh reads {GENERATED_CONFIG}, not {config_path}.",
            file=sys.stderr,
        )

    runner = runner_module.InstallRunner(project_root=PROJECT_ROOT)

    problems = runner.preflight(config)
    if problems:
        print("\nCannot start:", file=sys.stderr)
        for problem in problems:
            print(f"  {problem}", file=sys.stderr)
        return 1

    try:
        runner.start()
        outcome = tui.run_installation(runner)
    except KeyboardInterrupt:
        # The screen handles Ctrl-C itself; this is the last resort, so that a
        # terminal which delivered the signal anyway ends with a summary rather
        # than a traceback over a half-restored screen.
        runner.interrupt()
        runner.close()
        print("\nInterrupted. The installer was asked to stop.", file=sys.stderr)
        return 130
    finally:
        runner.close()

    print(f"\nDry run {outcome.name.lower()}.")
    if runner.model.log_file:
        print(f"Log: {runner.model.log_file}")
    if outcome is runner_module.Outcome.SUCCESS:
        return 0
    return 130 if outcome is runner_module.Outcome.INTERRUPTED else 1


def choose_front_end(args: argparse.Namespace) -> Callable[[Menu, Configuration], Action]:
    """The full screen when the terminal can take it, the prompts otherwise.

    Degrading on ImportError rather than failing is deliberate: a Python built
    without ``_curses`` must still be able to configure and start an installation.
    """
    if args.text:
        return run

    try:
        from . import tui
    except ImportError:
        return run

    if args.tui or tui.available():
        # The Install key says whether it will follow a dry run on screen or hand
        # the terminal over, so the screen has to know which was asked for.
        return functools.partial(tui.run, dry_run=args.dry_run)
    return run


def main(argv: list[str] | None = None) -> int:
    try:
        return _main(argv)
    except KeyboardInterrupt:
        # Ctrl-C anywhere, including before the interface is up, ends the way
        # quitting does rather than as a stack trace on a terminal that curses may
        # have been halfway through setting up.
        print("\nInterrupted. Nothing was written.", file=sys.stderr)
        return 130


def _main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config = load(args.config)

    if args.show:
        report(config)
        return 0 if constraints.is_installable(config) else 1

    front_end = choose_front_end(args)

    if front_end is run and not stdin_is_interactive():
        # Piped input is allowed rather than refused: the menu is plain prompts,
        # so it drives fine from a script, and that is what makes the whole flow
        # testable. Only exhausted input is an error.
        print("Reading answers from standard input.", file=sys.stderr)

    try:
        action = front_end(build_menu(), config)
    except EOFError:
        print(
            "\nInput ended before the menu was finished. Nothing was written.",
            file=sys.stderr,
        )
        return 2
    except KeyboardInterrupt:
        print("\nInterrupted. Nothing was written.", file=sys.stderr)
        return 130

    if action is Action.QUIT:
        print("\nNothing was written.")
        return 130

    config.save(args.config)
    print(f"\nWrote {args.config}")
    report(config)

    if action is Action.SAVE:
        print("\nRun the installation with:\n  sudo ./install.sh")
        return 0

    # A dry run is followed on screen; a real installation is handed the terminal,
    # exactly as before, because it has questions only the terminal can carry.
    if args.dry_run and front_end is not run and runner.supported():
        return follow_dry_run(args.config, config)

    return hand_over(args.config, dry_run=args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
