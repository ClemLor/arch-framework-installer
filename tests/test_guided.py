"""Tests for the guided flow as the CLI drives it."""

from __future__ import annotations

from pathlib import Path

import pytest

from arch_framework.lib.disk.source import FIXTURE_ENV_VAR
from arch_framework.lib.models import InstallConfig
from arch_framework.main import main
from arch_framework.profiles import default_config

FIXTURE = Path(__file__).parent / "fixtures" / "framework.json"


@pytest.fixture
def with_fixture_devices(monkeypatch):
    monkeypatch.setenv(FIXTURE_ENV_VAR, str(FIXTURE))
    from arch_framework.lib.disk.source import set_source

    set_source(None)
    yield
    set_source(None)


def keystrokes(monkeypatch, *values: str) -> None:
    stream = iter(values)
    monkeypatch.setattr("builtins.input", lambda *_: next(stream))


def test_missing_config_starts_from_defaults(
    monkeypatch, tmp_path: Path, with_fixture_devices
) -> None:
    """--config names both what to load and where to save. A path that does not
    exist yet is the normal first run, not an error."""
    keystrokes(monkeypatch, "q")
    target = tmp_path / "new.json"

    assert main(["--tui", "--renderer", "plain", "--config", str(target)]) == 130
    assert not target.exists(), "aborting must not write anything"


def test_save_writes_a_replayable_configuration(
    monkeypatch, tmp_path: Path, with_fixture_devices
) -> None:
    keystrokes(monkeypatch, "3", "1", "", "8", "clement", "y", "", "s")
    target = tmp_path / "saved.json"

    assert main(["--tui", "--renderer", "plain", "--config", str(target)]) == 0

    saved = InstallConfig.load(target)
    assert saved.disk.target_disk == "/dev/nvme0n1"
    assert saved.users.users[0].name == "clement"


def test_replay_is_byte_identical(
    monkeypatch, tmp_path: Path, with_fixture_devices
) -> None:
    """The saved file is the reproducibility artefact. Loading and saving it
    again must not perturb it."""
    target = tmp_path / "saved.json"
    default_config().save(target)
    original = target.read_text(encoding="utf-8")

    keystrokes(monkeypatch, "s")
    assert main(["--tui", "--renderer", "plain", "--config", str(target)]) == 0
    assert target.read_text(encoding="utf-8") == original


def test_a_reloaded_configuration_can_install_without_reanswering(
    monkeypatch, tmp_path: Path, with_fixture_devices
) -> None:
    """Loading a saved file and pressing Install must work. Requiring the menu
    to be walked again would make replay pointless."""
    target = tmp_path / "saved.json"
    payload = default_config().model_dump(mode="json")
    payload["users"]["users"] = [
        {"name": "clement", "sudo": True, "shell": "/usr/bin/fish", "groups": []}
    ]
    InstallConfig.model_validate(payload).save(target)

    keystrokes(monkeypatch, "i")
    # 2 is "configuration complete, installation not implemented yet", which is
    # the install path being reached — not the mandatory-entry guard refusing.
    assert main(["--tui", "--renderer", "plain", "--config", str(target)]) == 2


def test_a_fresh_run_cannot_install_the_placeholder_disk(
    monkeypatch, tmp_path: Path, with_fixture_devices
) -> None:
    """The profile ships a placeholder target so the document is valid. It must
    never be installed onto by someone who just pressed Install."""
    keystrokes(monkeypatch, "i", "q")
    target = tmp_path / "fresh.json"

    assert main(["--tui", "--renderer", "plain", "--config", str(target)]) == 130
    assert not target.exists()


def test_abort_returns_130_and_writes_nothing(
    monkeypatch, tmp_path: Path, with_fixture_devices
) -> None:
    keystrokes(monkeypatch, "3", "1", "", "q")
    target = tmp_path / "aborted.json"

    assert main(["--tui", "--renderer", "plain", "--config", str(target)]) == 130
    assert not target.exists()


def test_inspect_reports_without_a_config(with_fixture_devices) -> None:
    assert main(["--inspect"]) == 0


def test_no_mode_is_an_error() -> None:
    assert main([]) == 2


def test_a_broken_config_is_reported_not_raised(tmp_path: Path) -> None:
    broken = tmp_path / "broken.json"
    broken.write_text("{ not json", encoding="utf-8")
    assert main(["--inspect", "--config", str(broken)]) == 1
