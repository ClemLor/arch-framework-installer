from __future__ import annotations

from pathlib import Path

from arch_framework.lib.disk.source import FIXTURE_ENV_VAR, FixtureSource, get_source

FIXTURE = Path(__file__).parent / "fixtures" / "framework.json"


def test_flattens_partitions_under_their_disk(framework_source: FixtureSource) -> None:
    paths = {device["path"] for device in framework_source.block_devices()}
    assert {"/dev/nvme0n1", "/dev/nvme0n1p1", "/dev/nvme0n1p2", "/dev/sdb", "/dev/sdb1"} <= paths


def test_children_carry_a_parent_back_reference(framework_source: FixtureSource) -> None:
    partition = next(
        device
        for device in framework_source.block_devices()
        if device["path"] == "/dev/sdb1"
    )
    assert partition["pkname"] == "/dev/sdb"


def test_mount_targets(framework_source: FixtureSource) -> None:
    assert framework_source.mount_source("/run/archiso/bootmnt") == "/dev/sdb1"
    assert framework_source.mount_source("/nowhere") is None


def test_file_reads(framework_source: FixtureSource) -> None:
    assert framework_source.read_text("/sys/class/dmi/id/sys_vendor") == "Framework\n"
    assert framework_source.read_text("/absent") is None


def test_declared_files_count_as_existing_paths(framework_source: FixtureSource) -> None:
    assert framework_source.path_exists("/proc/meminfo")
    assert framework_source.path_exists("/run/archiso")
    assert not framework_source.path_exists("/absent")


def test_env_var_selects_the_fixture(monkeypatch) -> None:
    monkeypatch.setenv(FIXTURE_ENV_VAR, str(FIXTURE))
    source = get_source()
    assert isinstance(source, FixtureSource)
    assert source.mount_source("/run/archiso/bootmnt") == "/dev/sdb1"
