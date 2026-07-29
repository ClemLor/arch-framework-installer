"""The single gate for every system command.

This is the most important invariant in the project, inherited from the Bash
implementation: nothing mutates the system except through here, so that
dry-run, logging and failure handling behave identically everywhere.

Two operations, deliberately distinct:

``run``
    Mutating. Honours dry-run by *not* executing.

``capture``
    Read-only. **Always** executes, including in dry-run, because its output is
    consumed as a value. Returning a dry-run placeholder would silently corrupt
    every decision made from it — the exact bug the Bash version shipped with.

Markers go to stderr so a caller reading ``capture`` output never sees them.
"""

from __future__ import annotations

import shlex
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from . import log
from .exceptions import CommandError


def _render(argv: list[str]) -> str:
    return " ".join(shlex.quote(part) for part in argv)


@dataclass
class Result:
    """Outcome of a command, including the dry-run case."""

    argv: list[str]
    returncode: int = 0
    stdout: str = ""
    stderr: str = ""
    executed: bool = True

    @property
    def ok(self) -> bool:
        return self.returncode == 0


@dataclass
class CommandRunner:
    dry_run: bool = False
    verbose: bool = False
    #: Every mutating command that was requested, in order. Populated in both
    #: modes; this is what ``--dry-run`` reports and what the tests assert on.
    journal: list[list[str]] = field(default_factory=list)

    # -- mutating -----------------------------------------------------------

    def run(
        self,
        argv: list[str],
        *,
        check: bool = True,
        input_text: str | None = None,
        cwd: Path | None = None,
    ) -> Result:
        """Execute a command that may change the system."""
        self.journal.append(list(argv))

        if self.dry_run:
            log.info(f"[DRY-RUN] {_render(argv)}")
            return Result(argv=list(argv), executed=False)

        if self.verbose:
            log.info(f"[COMMAND] {_render(argv)}")

        completed = subprocess.run(
            argv,
            input=input_text,
            capture_output=True,
            text=True,
            cwd=cwd,
            check=False,
        )
        result = Result(
            argv=list(argv),
            returncode=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )

        if check and not result.ok:
            raise CommandError(list(argv), result.returncode, result.stderr)

        return result

    def run_critical(self, description: str, argv: list[str]) -> Result:
        """Execute a command whose failure must abort the installation."""
        log.info(description)
        try:
            return self.run(argv, check=True)
        except CommandError as exc:
            raise CommandError(list(argv), exc.returncode, exc.stderr) from exc

    # -- read-only ----------------------------------------------------------

    def capture(self, argv: list[str], *, check: bool = False) -> str:
        """Run a read-only command and return its stdout.

        Executes even in dry-run mode. Only pass commands that cannot change
        the system — nothing enforces that here.
        """
        if self.verbose:
            log.info(f"[CAPTURE] {_render(argv)}")

        if shutil.which(argv[0]) is None:
            if check:
                raise CommandError(list(argv), 127, f"{argv[0]}: not found")
            return ""

        completed = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            check=False,
        )

        if check and completed.returncode != 0:
            raise CommandError(list(argv), completed.returncode, completed.stderr)

        return completed.stdout


_runner = CommandRunner()


def get_runner() -> CommandRunner:
    return _runner


def set_runner(runner: CommandRunner) -> None:
    """Install the process-wide runner. Called once from the entry point."""
    global _runner
    _runner = runner
