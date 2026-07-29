"""Installer tests, driven entirely in dry-run against recorded devices.

The centrepiece is the golden journal: a full dry-run of every stage, with the
resulting command sequence compared against a committed file. That file pins
sgdisk's argument order and units, the cryptsetup options, the subvolume creation
order and the mount order — none of which can be checked any other way without a
machine to destroy. A diff on it is how any future change to the stages gets
reviewed.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from arch_framework.lib.command import CommandRunner
from arch_framework.lib.disk import filesystem, luks, partitioning
from arch_framework.lib.disk.source import FixtureSource, set_source
from arch_framework.lib.exceptions import (
    EnvironmentError_,
    StageError,
    UnsafeTargetError,
)
from arch_framework.lib.installer import Installer
from arch_framework.lib.models import Credentials, InstallConfig
from arch_framework.lib.state import InstallState, fingerprint
from arch_framework.profiles import default_config

GOLDEN = Path(__file__).parent / "golden" / "install-commands.txt"
FIXTURE = Path(__file__).parent / "fixtures" / "framework.json"


def ready_config() -> InstallConfig:
    payload = default_config().model_dump(mode="json")
    payload["users"]["users"] = [
        {"name": "clement", "sudo": True, "shell": "/usr/bin/fish", "groups": []}
    ]
    return InstallConfig.model_validate(payload)


def ready_credentials() -> Credentials:
    return Credentials(
        user_passwords={"clement": "secret"}, encryption_passphrase="passphrase"
    )


@pytest.fixture
def installed(framework_source: FixtureSource, tmp_path: Path):
    set_source(framework_source)
    config = ready_config()
    runner = CommandRunner(dry_run=True)
    state = InstallState(path=tmp_path / "state.json", config_fingerprint=fingerprint(config))
    installer = Installer(
        config, ready_credentials(), runner=runner, state=state, interactive=False
    )
    return installer, runner


# -- golden journal ---------------------------------------------------------


def test_full_dry_run_matches_the_golden_command_sequence(installed, capsys) -> None:
    installer, runner = installed
    assert installer.run() == 0

    rendered = "\n".join(" ".join(argv) for argv in runner.journal) + "\n"

    if not GOLDEN.is_file():  # pragma: no cover - first run only
        GOLDEN.parent.mkdir(parents=True, exist_ok=True)
        GOLDEN.write_text(rendered, encoding="utf-8")
        pytest.fail(f"wrote a new golden file at {GOLDEN}; review it and re-run")

    expected = GOLDEN.read_text(encoding="utf-8")
    assert rendered == expected, (
        "the command sequence changed. Review the diff, and update "
        f"{GOLDEN.name} only if the change is intended."
    )


# -- ordering properties ----------------------------------------------------


def order(journal: list[list[str]], *needles: str) -> list[int]:
    positions = []
    for needle in needles:
        positions.append(
            next(
                index
                for index, argv in enumerate(journal)
                if needle in " ".join(argv)
            )
        )
    return positions


def test_recovery_key_is_added_before_the_tpm2_is_enrolled(installed) -> None:
    """A TPM2 seal can be invalidated by a firmware update. Enrolling before a
    recovery key exists leaves a window where the machine can be lost."""
    installer, runner = installed
    installer.run()

    add_key, enroll = order(runner.journal, "luksAddKey", "--tpm2-device=auto")
    assert add_key < enroll


def test_the_container_is_formatted_before_the_filesystem(installed) -> None:
    installer, runner = installed
    installer.run()

    luks_format, mkfs = order(runner.journal, "luksFormat", "mkfs.btrfs")
    assert luks_format < mkfs


def test_root_subvolume_is_mounted_before_the_others(installed) -> None:
    """Every other subvolume mounts inside @."""
    installer, runner = installed
    installer.run()

    mounts = [
        argv for argv in runner.journal if argv[0] == "mount" and "subvol=" in " ".join(argv)
    ]
    assert "subvol=@," in " ".join(mounts[0])


def test_packages_are_installed_before_the_bootloader(installed) -> None:
    installer, runner = installed
    installer.run()

    pacstrap, limine_copy = order(runner.journal, "pacstrap", "BOOTX64.EFI")
    assert pacstrap < limine_copy


def test_partitioning_precedes_everything_destructive(installed) -> None:
    installer, runner = installed
    installer.run()
    assert runner.journal[0][0] == "wipefs"


def test_vconsole_is_written_before_the_initramfs_is_built(installed) -> None:
    """sd-vconsole reads /etc/vconsole.conf at build time. A keymap that lands
    afterwards means a passphrase prompt in the wrong layout — the failure
    boot.md documents and nothing else would catch."""
    installer, runner = installed
    installer.run()

    assert any(path.endswith("etc/vconsole.conf") for path in installer.target.written)

    # configure.apply writes every file, then runs the commands that consume
    # them, so pinning the build after locale-gen pins it after the writes too.
    build, locale_gen = (
        next(
            index
            for index, argv in enumerate(runner.journal)
            if needle in " ".join(argv)
        )
        for needle in ("mkinitcpio --allpresets", "locale-gen")
    )
    assert locale_gen < build


def test_only_one_dhcp_client_is_enabled(installed) -> None:
    """iwd and dhcpcd both do DHCP. Enabling both makes the first boot's network
    behaviour depend on which one wins the interface."""
    installer, runner = installed
    installer.run()

    enabled = [
        argv[-1] for argv in runner.journal if "systemctl" in argv and "enable" in argv
    ]
    assert "dhcpcd" not in enabled
    assert "systemd-networkd" in enabled
    assert "iwd" in enabled

    iwd_config = next(
        content
        for path, content in installer.target.written.items()
        if path.endswith("etc/iwd/main.conf")
    )
    assert "EnableNetworkConfiguration=false" in iwd_config


# -- sgdisk units -----------------------------------------------------------


def test_sgdisk_never_receives_mib() -> None:
    """sgdisk accepts K/M/G/T/P and rejects "MiB" outright. This was a real bug
    in the Bash implementation, latent because the commands were only printed."""
    commands = partitioning.partition_commands(default_config().disk)
    rendered = " ".join(" ".join(argv) for argv in commands)
    assert "MiB" not in rendered
    assert "--new=1:1M:1025M" in rendered


# -- the safety re-check ----------------------------------------------------


def test_partitioning_refuses_the_live_medium(framework_source: FixtureSource) -> None:
    """Re-checked here, not inherited from the menu: a configuration can be
    hand-written, copied between machines, or replayed against different
    hardware."""
    set_source(framework_source)
    payload = ready_config().model_dump(mode="json")
    payload["disk"]["target_disk"] = "/dev/sdb"
    payload["disk"]["minimum_disk_size"] = "16GiB"
    config = InstallConfig.model_validate(payload)

    with pytest.raises(UnsafeTargetError, match="live medium"):
        partitioning.partition(config.disk, runner=CommandRunner(dry_run=True))


def test_the_guard_fires_even_in_dry_run(framework_source: FixtureSource) -> None:
    """Dry-run must not be a way to rehearse something that would be refused."""
    set_source(framework_source)
    payload = ready_config().model_dump(mode="json")
    payload["disk"]["target_disk"] = "/dev/nvme0n1p1"
    config = InstallConfig.model_validate(payload)

    with pytest.raises(UnsafeTargetError):
        partitioning.partition(config.disk, runner=CommandRunner(dry_run=True))


# -- derived values ---------------------------------------------------------


def test_dry_run_uuids_are_marked_placeholders() -> None:
    """blkid returns nothing in a dry run because the filesystem was never made.
    Rendering fstab with blanks would make the rehearsal unreviewable."""
    runner = CommandRunner(dry_run=True)
    uuid = luks.partition_uuid("/dev/nvme0n1p2", runner=runner)
    assert uuid == "<UUID-of-/dev/nvme0n1p2>"


def test_dry_run_resume_offset_is_a_marked_placeholder() -> None:
    runner = CommandRunner(dry_run=True)
    assert filesystem.resume_offset(runner=runner) == "<resume-offset>"


# -- preflight --------------------------------------------------------------


def test_missing_passphrase_is_refused_before_anything_runs(
    framework_source: FixtureSource, tmp_path: Path
) -> None:
    set_source(framework_source)
    config = ready_config()
    runner = CommandRunner(dry_run=True)
    installer = Installer(
        config,
        Credentials(user_passwords={"clement": "x"}),
        runner=runner,
        state=InstallState(path=tmp_path / "s.json", config_fingerprint=fingerprint(config)),
        interactive=False,
    )

    with pytest.raises(StageError, match="passphrase"):
        installer.preflight()

    assert runner.journal == [], "nothing may run before preflight passes"


def test_missing_user_password_is_reported_by_the_model() -> None:
    config = ready_config()
    assert Credentials().missing_for(config.users) == ["clement"]


# -- resumability -----------------------------------------------------------


def test_completed_stages_are_skipped(framework_source: FixtureSource, tmp_path: Path) -> None:
    set_source(framework_source)
    config = ready_config()
    runner = CommandRunner(dry_run=True)
    state = InstallState(
        path=tmp_path / "state.json",
        config_fingerprint=fingerprint(config),
        completed=["partition", "encrypt", "recovery_key"],
    )
    Installer(
        config, ready_credentials(), runner=runner, state=state, interactive=False
    ).run()

    rendered = " ".join(" ".join(argv) for argv in runner.journal)
    assert "wipefs" not in rendered
    assert "luksFormat" not in rendered
    assert "mkfs.btrfs" in rendered


def test_state_from_a_different_configuration_is_refused(tmp_path: Path) -> None:
    """Half a system built to one layout and half to another is worse than
    starting again."""
    path = tmp_path / "state.json"
    path.write_text('{"config_fingerprint": "deadbeef", "completed": ["partition"]}')

    with pytest.raises(StageError, match="different configuration"):
        InstallState.load_or_new(ready_config(), path)


def test_state_survives_a_round_trip(tmp_path: Path) -> None:
    config = ready_config()
    path = tmp_path / "state.json"
    state = InstallState.load_or_new(config, path)
    state.mark_done("partition")

    assert InstallState.load_or_new(config, path).is_done("partition")


def test_unreadable_state_starts_over(tmp_path: Path) -> None:
    path = tmp_path / "state.json"
    path.write_text("not json", encoding="utf-8")
    assert InstallState.load_or_new(ready_config(), path).completed == []


def test_dry_run_does_not_record_progress(installed) -> None:
    """A rehearsal must not make the real run skip stages."""
    installer, _ = installed
    installer.run()
    assert installer.state.completed == []


# -- the fixture guard ------------------------------------------------------


def test_a_real_install_refuses_recorded_devices(
    framework_source: FixtureSource, tmp_path: Path
) -> None:
    """Recorded devices describe another machine. Partitioning a real disk from
    facts read out of a file is never right — and without this, a test that
    drives the CLI could reach wipefs on the developer's own disk."""
    set_source(framework_source)
    config = ready_config()
    runner = CommandRunner(dry_run=False)
    installer = Installer(
        config,
        ready_credentials(),
        runner=runner,
        state=InstallState(
            path=tmp_path / "s.json", config_fingerprint=fingerprint(config)
        ),
        interactive=False,
    )

    with pytest.raises(EnvironmentError_, match="fixture"):
        installer.preflight()

    assert runner.journal == []


def test_the_keyfile_name_is_deterministic() -> None:
    """It appears in the command journal, and a journal that varies between runs
    cannot be compared against a golden file."""
    assert "recovery" in str(luks.RECOVERY_KEYFILE)
    assert str(luks.RECOVERY_KEYFILE).startswith("/run/")
