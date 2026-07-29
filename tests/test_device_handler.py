"""Tests for the destructive-action guard.

Every rejection reason is asserted separately. The guards are independent in the
implementation, so a single combined "sdb is refused" test could pass while
three of the four were broken.
"""

from __future__ import annotations

import pytest

from arch_framework.lib.disk import DeviceHandler, FixtureSource
from arch_framework.lib.models import SafetyStatus, Size, Transport

TARGET = "/dev/nvme0n1"
LIVE = "/dev/sdb"


@pytest.fixture
def handler(framework_source: FixtureSource) -> DeviceHandler:
    return DeviceHandler(framework_source)


# -- enumeration ------------------------------------------------------------


def test_lists_only_whole_disks(handler: DeviceHandler) -> None:
    assert handler.disks() == [TARGET, LIVE]


def test_partition_is_not_a_whole_disk(handler: DeviceHandler) -> None:
    assert handler.is_whole_disk(TARGET)
    assert not handler.is_whole_disk("/dev/nvme0n1p1")


def test_accepts_a_bare_device_name(handler: DeviceHandler) -> None:
    """Callers should not have to know whether lsblk was run with --paths."""
    assert handler.is_whole_disk("nvme0n1")


def test_unknown_device_is_absent(handler: DeviceHandler) -> None:
    assert not handler.exists("/dev/nonexistent")


# -- parent walk ------------------------------------------------------------


def test_resolves_partition_to_its_disk(handler: DeviceHandler) -> None:
    assert handler.resolve_parent_disk("/dev/nvme0n1p2") == TARGET


def test_resolving_a_disk_returns_itself(handler: DeviceHandler) -> None:
    assert handler.resolve_parent_disk(TARGET) == TARGET


def test_walks_through_a_device_mapper_node() -> None:
    """A LUKS mapping sits on a partition, which sits on a disk: two steps."""
    source = FixtureSource(
        {
            "blockdevices": [
                {
                    "path": "/dev/nvme0n1",
                    "name": "/dev/nvme0n1",
                    "type": "disk",
                    "children": [
                        {
                            "path": "/dev/nvme0n1p2",
                            "name": "/dev/nvme0n1p2",
                            "type": "part",
                            "children": [
                                {
                                    "path": "/dev/mapper/cryptroot",
                                    "name": "/dev/mapper/cryptroot",
                                    "type": "crypt",
                                }
                            ],
                        }
                    ],
                }
            ]
        }
    )
    assert DeviceHandler(source).resolve_parent_disk("/dev/mapper/cryptroot") == (
        "/dev/nvme0n1"
    )


def test_walk_terminates_on_a_cycle() -> None:
    """The walk runs immediately before destroying a disk. It does not hang."""
    source = FixtureSource(
        {
            "blockdevices": [
                {"path": "/dev/a", "name": "/dev/a", "type": "part", "pkname": "b"},
                {"path": "/dev/b", "name": "/dev/b", "type": "part", "pkname": "a"},
            ]
        }
    )
    assert DeviceHandler(source).resolve_parent_disk("/dev/a") is None


def test_orphan_partition_resolves_to_nothing() -> None:
    source = FixtureSource(
        {"blockdevices": [{"path": "/dev/sdz1", "name": "/dev/sdz1", "type": "part"}]}
    )
    assert DeviceHandler(source).resolve_parent_disk("/dev/sdz1") is None


# -- live medium ------------------------------------------------------------


def test_finds_the_live_medium(handler: DeviceHandler) -> None:
    assert handler.live_medium_source() == "/dev/sdb1"
    assert handler.live_medium_disk() == LIVE


def test_live_medium_checked_before_the_root_filesystem() -> None:
    """The ISO's root is an overlay, so /run/archiso/bootmnt is what identifies
    the physical stick. Falling through to / would find nothing usable."""
    source = FixtureSource(
        {
            "blockdevices": [
                {
                    "path": "/dev/sdb",
                    "name": "/dev/sdb",
                    "type": "disk",
                    "children": [
                        {"path": "/dev/sdb1", "name": "/dev/sdb1", "type": "part"}
                    ],
                }
            ],
            "mounts": {"/": "airootfs", "/run/archiso/bootmnt": "/dev/sdb1"},
            "paths": ["/run/archiso/bootmnt"],
        }
    )
    assert DeviceHandler(source).live_medium_disk() == "/dev/sdb"


def test_no_live_medium_on_an_installed_system() -> None:
    source = FixtureSource(
        {
            "blockdevices": [
                {"path": "/dev/nvme0n1", "name": "/dev/nvme0n1", "type": "disk"}
            ],
            "mounts": {"/": "/dev/nvme0n1p2"},
        }
    )
    handler = DeviceHandler(source)
    # / resolves to the installed disk, which is exactly why an installed system
    # must never be treated as a live medium by accident.
    assert handler.live_medium_source() == "/dev/nvme0n1p2"


# -- the four independent rejections ---------------------------------------


def test_rejects_the_live_medium(handler: DeviceHandler) -> None:
    verdict = handler.safety(LIVE)
    assert verdict.status is SafetyStatus.REJECTED
    assert "live medium" in verdict.reason
    assert not verdict.writable


def test_rejects_usb_transport() -> None:
    source = FixtureSource(
        {
            "blockdevices": [
                {
                    "path": "/dev/sdc",
                    "name": "/dev/sdc",
                    "type": "disk",
                    "tran": "usb",
                    "rm": False,
                }
            ]
        }
    )
    verdict = DeviceHandler(source).safety("/dev/sdc")
    assert verdict.status is SafetyStatus.REJECTED
    assert "USB" in verdict.reason


def test_rejects_removable_media() -> None:
    source = FixtureSource(
        {
            "blockdevices": [
                {
                    "path": "/dev/mmcblk0",
                    "name": "/dev/mmcblk0",
                    "type": "disk",
                    "tran": "mmc",
                    "rm": True,
                }
            ]
        }
    )
    verdict = DeviceHandler(source).safety("/dev/mmcblk0")
    assert verdict.status is SafetyStatus.REJECTED
    assert "removable" in verdict.reason


def test_rejects_a_partition_as_target(handler: DeviceHandler) -> None:
    verdict = handler.safety("/dev/nvme0n1p1")
    assert verdict.status is SafetyStatus.REJECTED
    assert "whole disk" in verdict.reason


def test_rejects_a_device_that_does_not_exist(handler: DeviceHandler) -> None:
    verdict = handler.safety("/dev/nonexistent")
    assert verdict.status is SafetyStatus.REJECTED
    assert "not found" in verdict.reason


def test_rejects_a_mounted_disk_for_writing() -> None:
    source = FixtureSource(
        {
            "blockdevices": [
                {
                    "path": "/dev/nvme0n1",
                    "name": "/dev/nvme0n1",
                    "type": "disk",
                    "tran": "nvme",
                    "rm": False,
                    "children": [
                        {
                            "path": "/dev/nvme0n1p2",
                            "name": "/dev/nvme0n1p2",
                            "type": "part",
                            "mountpoints": ["/mnt/data"],
                        }
                    ],
                }
            ]
        }
    )
    assert DeviceHandler(source).safety("/dev/nvme0n1").status is SafetyStatus.REJECTED


def test_mounted_disk_is_only_a_warning_in_read_only_modes() -> None:
    source = FixtureSource(
        {
            "blockdevices": [
                {
                    "path": "/dev/nvme0n1",
                    "name": "/dev/nvme0n1",
                    "type": "disk",
                    "tran": "nvme",
                    "rm": False,
                    "children": [
                        {
                            "path": "/dev/nvme0n1p2",
                            "name": "/dev/nvme0n1p2",
                            "type": "part",
                            "mountpoints": ["/mnt/data"],
                        }
                    ],
                }
            ]
        }
    )
    verdict = DeviceHandler(source).safety("/dev/nvme0n1", read_only_mode=True)
    assert verdict.status is SafetyStatus.WARNING
    assert not verdict.writable, "a warning must still not authorise writing"


def test_read_only_mode_does_not_excuse_the_live_medium(handler: DeviceHandler) -> None:
    """Relaxing the mount check must not relax anything else."""
    verdict = handler.safety(LIVE, read_only_mode=True)
    assert verdict.status is SafetyStatus.REJECTED


# -- acceptance -------------------------------------------------------------


def test_accepts_the_intended_internal_disk(handler: DeviceHandler) -> None:
    verdict = handler.safety(TARGET)
    assert verdict.status is SafetyStatus.ELIGIBLE
    assert verdict.writable
    assert str(verdict) == "Eligible"


def test_candidate_list_excludes_the_live_medium(handler: DeviceHandler) -> None:
    assert handler.installation_candidates() == [TARGET]


# -- reported facts ---------------------------------------------------------


def test_info_reports_observed_properties(handler: DeviceHandler) -> None:
    info = handler.info(TARGET)
    assert info is not None
    assert info.model == "WD_BLACK SN770 1TB"
    assert info.transport is Transport.NVME
    assert info.size == Size.from_bytes(1000204886016)
    assert info.removable is False
    assert info.rotational is False
    assert info.partition_table == "gpt"
    assert info.has_luks, "the existing crypto_LUKS partition should be reported"
    assert not info.is_live_medium
    assert not info.mounted


def test_info_flags_the_live_medium(handler: DeviceHandler) -> None:
    info = handler.info(LIVE)
    assert info is not None
    assert info.is_live_medium
    assert info.transport is Transport.USB
    assert info.removable is True
    assert info.mountpoints == ["/run/archiso/bootmnt"]


def test_info_of_absent_device_is_none(handler: DeviceHandler) -> None:
    assert handler.info("/dev/nonexistent") is None


def test_nvme_without_reported_transport_is_still_nvme() -> None:
    source = FixtureSource(
        {"blockdevices": [{"path": "/dev/nvme1n1", "name": "/dev/nvme1n1", "type": "disk"}]}
    )
    assert DeviceHandler(source).transport("/dev/nvme1n1") is Transport.NVME


@pytest.mark.parametrize(("raw", "expected"), [(1, True), (0, False), ("1", True)])
def test_removable_flag_tolerates_integer_form(raw: object, expected: bool) -> None:
    """Older lsblk reports RM as 0/1 rather than as a JSON boolean."""
    source = FixtureSource(
        {"blockdevices": [{"path": "/dev/sdx", "name": "/dev/sdx", "type": "disk", "rm": raw}]}
    )
    assert DeviceHandler(source).is_removable("/dev/sdx") is expected
