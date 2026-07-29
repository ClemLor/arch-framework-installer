"""Writing to the target system.

Commands are not the only thing that changes a system: writing ``/mnt/etc/fstab``
is just as destructive as running ``mkfs``. So file writes go through the same
gate, honour dry-run, and are recorded — otherwise ``--dry-run`` would silently
create files while claiming to change nothing.

In dry-run the intended contents are printed, because a plan that says "would
write fstab" without showing what is a plan nobody can check.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

from . import log
from .command import CommandRunner, get_runner

TARGET_ROOT = Path("/mnt")


@dataclass
class TargetSystem:
    """The system being assembled under /mnt."""

    root: Path = TARGET_ROOT
    runner: CommandRunner | None = None
    #: Every file that was written, path to contents. Asserted by the tests and
    #: shown by --dry-run.
    written: dict[str, str] = field(default_factory=dict)

    def _runner(self) -> CommandRunner:
        return self.runner or get_runner()

    def path(self, relative: str) -> Path:
        return self.root / relative.lstrip("/")

    # -- files --------------------------------------------------------------

    def write(self, relative: str, content: str, *, mode: int = 0o644) -> None:
        target = self.path(relative)
        self.written[str(target)] = content
        runner = self._runner()

        if runner.dry_run:
            # Body to stderr with the header, not stdout: stdout stays clean so
            # a caller can still capture real data from it, and the header and
            # its contents stay in order instead of interleaving across streams.
            log.info(f"[DRY-RUN] write {target} (mode {mode:o}):")
            for line in content.splitlines():
                print(f"    | {line}", file=sys.stderr)
            return

        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        target.chmod(mode)
        log.info(f"Wrote {target}")

    def append(self, relative: str, content: str) -> None:
        target = self.path(relative)
        existing = self.written.get(str(target), "")
        self.written[str(target)] = existing + content
        runner = self._runner()

        if runner.dry_run:
            log.info(f"[DRY-RUN] append to {target}:")
            for line in content.splitlines():
                print(f"    | {line}", file=sys.stderr)
            return

        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("a", encoding="utf-8") as handle:
            handle.write(content)
        log.info(f"Appended to {target}")

    # -- commands inside the target -----------------------------------------

    def chroot(
        self,
        argv: list[str],
        *,
        input_text: str | None = None,
        stream: bool = False,
        check: bool = True,
    ):
        """Run a command inside the target system."""
        return self._runner().run(
            ["arch-chroot", str(self.root), *argv],
            input_text=input_text,
            stream=stream,
            check=check,
        )

    def chroot_critical(self, description: str, argv: list[str], *, stream: bool = False):
        log.info(description)
        return self.chroot(argv, stream=stream, check=True)

    def enable_service(self, name: str) -> None:
        self.chroot_critical(f"Enabling {name}", ["systemctl", "enable", name])
