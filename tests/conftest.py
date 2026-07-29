from __future__ import annotations

from pathlib import Path

import pytest

from arch_framework.lib.command import CommandRunner, set_runner
from arch_framework.lib.disk.source import FixtureSource, set_source

FIXTURE_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def framework_source() -> FixtureSource:
    return FixtureSource.from_file(FIXTURE_DIR / "framework.json")


@pytest.fixture(autouse=True)
def isolated_globals():
    """Never let a test see the real machine or the real runner.

    The safety layer's whole point is refusing to write to the wrong disk; a
    test that silently fell through to SystemSource would be testing nothing on
    a developer's laptop and something dangerous on a live ISO.
    """
    set_source(None)
    set_runner(CommandRunner(dry_run=True))
    yield
    set_source(None)
    set_runner(CommandRunner())
