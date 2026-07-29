from __future__ import annotations

from pathlib import Path

import pytest

from arch_framework.lib.disk.source import (
    FIXTURE_ENV_VAR,
    PARENT_KEY,
    FixtureSource,
    get_source,
    normalise_device_name,
)

FIXTURE = Path(__file__).parent / "fixtures" / "framework.json"


def test_flattens_partitions_under_their_disk(framework_source: FixtureSource) -> None:
    paths = {device["path"] for device in framework_source.block_devices()}
    assert {"/dev/nvme0n1", "/dev/nvme0n1p1", "/dev/nvme0n1p2", "/dev/sdb", "/dev/sdb1"} <= paths


def find(source: FixtureSource, path: str) -> dict:
    return next(
        device for device in source.block_devices() if device["path"] == path
    )


def test_children_carry_a_parent_back_reference(framework_source: FixtureSource) -> None:
    assert find(framework_source, "/dev/sdb1")[PARENT_KEY] == "/dev/sdb"


def test_parent_reference_ignores_lsblk_pkname_form(
    framework_source: FixtureSource,
) -> None:
    """lsblk's own pkname may or may not be /dev/-prefixed depending on version
    and --paths handling. The recorded parent must be the prefixed path either
    way, so nothing downstream has to care."""
    bare = find(framework_source, "/dev/nvme0n1p1")
    prefixed = find(framework_source, "/dev/nvme0n1p2")
    assert bare["pkname"] == "nvme0n1"
    assert prefixed["pkname"] == "/dev/nvme0n1"
    assert bare[PARENT_KEY] == prefixed[PARENT_KEY] == "/dev/nvme0n1"


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("sdb", "/dev/sdb"),
        ("/dev/sdb", "/dev/sdb"),
        ("nvme0n1p2", "/dev/nvme0n1p2"),
        (None, None),
        ("", None),
    ],
)
def test_normalise_device_name(value: str | None, expected: str | None) -> None:
    assert normalise_device_name(value) == expected


def test_binary_files_survive_the_fixture(framework_source: FixtureSource) -> None:
    """efivars are binary. Storing them as JSON text would corrupt the offsets
    that the Secure Boot check indexes into."""
    raw = framework_source.read_bytes(
        "/sys/firmware/efi/efivars/"
        "SecureBoot-8be4df61-93ca-11d2-aa0d-00e098032b8c"
    )
    assert raw == b"\x06\x00\x00\x00\x01"
    assert len(raw) == 5


def test_read_bytes_of_a_text_file(framework_source: FixtureSource) -> None:
    assert framework_source.read_bytes("/sys/class/dmi/id/sys_vendor") == b"Framework\n"


def test_read_bytes_of_absent_file(framework_source: FixtureSource) -> None:
    assert framework_source.read_bytes("/absent") is None


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
