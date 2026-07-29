from __future__ import annotations

import sys

import pytest

from arch_framework.lib.command import CommandRunner
from arch_framework.lib.exceptions import CommandError


def test_dry_run_does_not_execute() -> None:
    runner = CommandRunner(dry_run=True)
    result = runner.run([sys.executable, "-c", "raise SystemExit(1)"])
    assert result.executed is False
    assert result.ok


def test_dry_run_records_the_command() -> None:
    runner = CommandRunner(dry_run=True)
    runner.run(["sgdisk", "--zap-all", "/dev/null"])
    assert runner.journal == [["sgdisk", "--zap-all", "/dev/null"]]


def test_dry_run_marker_goes_to_stderr(capsys: pytest.CaptureFixture[str]) -> None:
    """The Bash version printed markers on stdout, so $(run_command ...) captured
    the marker as its value. Nothing may reach stdout from here."""
    CommandRunner(dry_run=True).run(["mkfs.btrfs", "/dev/null"])
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "DRY-RUN" in captured.err


def test_capture_executes_even_in_dry_run() -> None:
    """capture is read-only and its output is data. A placeholder would silently
    corrupt every decision made from it."""
    runner = CommandRunner(dry_run=True)
    out = runner.capture([sys.executable, "-c", "print('real-value')"])
    assert out.strip() == "real-value"


def test_capture_does_not_pollute_stdout(capsys: pytest.CaptureFixture[str]) -> None:
    runner = CommandRunner(dry_run=True, verbose=True)
    runner.capture([sys.executable, "-c", "pass"])
    assert capsys.readouterr().out == ""


def test_capture_of_missing_binary_returns_empty() -> None:
    assert CommandRunner().capture(["definitely-not-a-real-binary"]) == ""


def test_capture_of_missing_binary_can_raise() -> None:
    with pytest.raises(CommandError):
        CommandRunner().capture(["definitely-not-a-real-binary"], check=True)


def test_failure_raises_by_default() -> None:
    with pytest.raises(CommandError) as excinfo:
        CommandRunner().run([sys.executable, "-c", "raise SystemExit(3)"])
    assert excinfo.value.returncode == 3


def test_failure_can_be_tolerated() -> None:
    result = CommandRunner().run(
        [sys.executable, "-c", "raise SystemExit(3)"], check=False
    )
    assert result.returncode == 3
    assert not result.ok


def test_command_error_message_includes_the_command() -> None:
    error = CommandError(["sgdisk", "--new=1:1M:1025M"], 1, "boom")
    assert "sgdisk" in str(error)
    assert "boom" in str(error)
