from __future__ import annotations

from arch_framework.lib.disk.source import FixtureSource
from arch_framework.lib.hardware import SECURE_BOOT_EFIVAR, Hardware
from arch_framework.lib.models import Size


def test_identifies_the_machine(framework_source: FixtureSource) -> None:
    info = Hardware(framework_source).info()
    assert info.vendor == "Framework"
    assert info.is_framework
    assert "Laptop 13" in info.machine
    assert info.machine.endswith("A7")


def test_reads_cpu_and_memory(framework_source: FixtureSource) -> None:
    hardware = Hardware(framework_source)
    assert "Ryzen 7 7840U" in hardware.cpu()
    memory = hardware.memory()
    assert memory is not None
    assert Size.parse("31GiB") <= memory <= Size.parse("32GiB")


def test_detects_uefi_and_secure_boot(framework_source: FixtureSource) -> None:
    hardware = Hardware(framework_source)
    assert hardware.is_uefi()
    # Byte 4 of the efivar carries the state; bytes 0-3 are attributes.
    assert hardware.secure_boot_state() == "Enabled"


def test_secure_boot_disabled() -> None:
    source = FixtureSource(
        {
            "files_base64": {SECURE_BOOT_EFIVAR: "BgAAAAA="},
            "paths": ["/sys/firmware/efi/efivars"],
        }
    )
    assert Hardware(source).secure_boot_state() == "Disabled"


def test_secure_boot_unknown_when_efivar_is_truncated() -> None:
    source = FixtureSource(
        {
            "files_base64": {SECURE_BOOT_EFIVAR: "BgAA"},
            "paths": ["/sys/firmware/efi/efivars"],
        }
    )
    assert Hardware(source).secure_boot_state() == "Unknown"


def test_secure_boot_unavailable_without_uefi() -> None:
    source = FixtureSource({"files_base64": {SECURE_BOOT_EFIVAR: "BgAAAAE="}})
    assert Hardware(source).secure_boot_state() == "Unavailable"


def test_detects_the_live_environment(framework_source: FixtureSource) -> None:
    assert Hardware(framework_source).is_live_environment()


def test_installed_system_is_not_a_live_environment() -> None:
    source = FixtureSource(
        {
            "blockdevices": [],
            "mounts": {"/": "/dev/nvme0n1p2"},
            "files": {},
            "paths": ["/etc/arch-release", "/sys/firmware/efi/efivars"],
        }
    )
    assert Hardware(source).is_live_environment() is False


def test_missing_facts_degrade_to_unknown() -> None:
    hardware = Hardware(FixtureSource({}))
    info = hardware.info()
    assert info.vendor == "Unknown"
    assert info.cpu == "Unknown"
    assert info.memory is None
    assert info.uefi is False
    assert info.secure_boot == "Unavailable"
    assert info.is_framework is False
