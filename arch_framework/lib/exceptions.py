"""Exception hierarchy.

Every failure that should abort an installation is an :class:`InstallerError`,
so the entry point can distinguish an expected refusal (wrong environment,
unsafe target, bad config) from a genuine bug and report accordingly.
"""

from __future__ import annotations


class InstallerError(Exception):
    """Base class for all expected, reportable failures."""


class ConfigError(InstallerError):
    """The configuration is missing, malformed or internally inconsistent."""


class EnvironmentError_(InstallerError):
    """The host is not a valid place to run an installation."""


class UnsafeTargetError(InstallerError):
    """The requested target disk must not be written to."""


class CommandError(InstallerError):
    """A system command failed."""

    def __init__(self, argv: list[str], returncode: int, stderr: str = "") -> None:
        self.argv = argv
        self.returncode = returncode
        self.stderr = stderr
        rendered = " ".join(argv)
        message = f"command failed (exit {returncode}): {rendered}"
        if stderr.strip():
            message = f"{message}\n{stderr.strip()}"
        super().__init__(message)


class StageError(InstallerError):
    """An installation stage could not complete."""
