from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from arch_framework.lib.exceptions import ConfigError
from arch_framework.lib.models import EncryptionConfig, InstallConfig, Size, SystemConfig
from arch_framework.profiles import default_config


def override(base: InstallConfig, **disk_changes: object) -> InstallConfig:
    payload = base.model_dump(mode="json")
    payload["disk"].update(disk_changes)
    return InstallConfig.model_validate(payload)


# -- hibernation / @swap ----------------------------------------------------


def test_hibernation_requires_swap_subvolume() -> None:
    payload = default_config(hibernation=False).model_dump(mode="json")
    payload["swap"]["hibernation_enabled"] = True
    with pytest.raises(ValidationError, match="@swap"):
        InstallConfig.model_validate(payload)


def test_swap_subvolume_not_required_without_hibernation() -> None:
    config = default_config(hibernation=False)
    assert "@swap" not in config.disk.subvolumes
    assert config.swap.hibernation_enabled is False


# -- disk layout ------------------------------------------------------------


def test_target_disk_must_be_absolute() -> None:
    with pytest.raises(ValidationError):
        override(default_config(), target_disk="nvme0n1")


@pytest.mark.parametrize("efi", ["256MiB", "8GiB"])
def test_efi_size_bounds(efi: str) -> None:
    with pytest.raises(ValidationError):
        override(default_config(), efi_size=efi)


def test_required_subvolumes_enforced() -> None:
    with pytest.raises(ValidationError, match="@home"):
        override(
            default_config(),
            subvolumes=["@", "@snapshots", "@cache", "@log", "@swap"],
        )


@pytest.mark.parametrize("label", ["", "bad label", "lab/el"])
def test_partition_label_charset(label: str) -> None:
    with pytest.raises(ValidationError):
        override(default_config(), efi_label=label)


@pytest.mark.parametrize(
    ("disk", "first", "second"),
    [
        ("/dev/nvme0n1", "/dev/nvme0n1p1", "/dev/nvme0n1p2"),
        ("/dev/mmcblk0", "/dev/mmcblk0p1", "/dev/mmcblk0p2"),
        ("/dev/sda", "/dev/sda1", "/dev/sda2"),
    ],
)
def test_partition_paths(disk: str, first: str, second: str) -> None:
    config = override(default_config(), target_disk=disk)
    assert config.disk.efi_partition == first
    assert config.disk.system_partition == second


def test_efi_ends_one_mib_past_its_size() -> None:
    """The first partition starts at 1MiB for alignment, so a 1GiB EFI ends at
    1025MiB and the size on disk is still exactly 1GiB."""
    config = default_config()
    assert config.disk.efi_end.sgdisk() == "1025M"


def test_mount_options_carry_compression() -> None:
    assert default_config().disk.mount_options == "noatime,compress=zstd:3"


# -- capacity ---------------------------------------------------------------


def test_capacity_accepts_a_disk_that_fits() -> None:
    config = default_config()
    config.validate_capacity(Size.parse("1TiB"))


def test_capacity_rejects_disk_below_minimum() -> None:
    with pytest.raises(ConfigError, match="too small"):
        default_config().validate_capacity(Size.parse("32GiB"))


def test_capacity_rejects_layout_that_starves_root() -> None:
    """A disk can clear minimum_disk_size and still leave no usable root once
    the swapfile is carved out. That was the gap in the Bash version."""
    config = override(default_config(), minimum_disk_size="32GiB")
    with pytest.raises(ConfigError, match="cannot hold the planned layout"):
        config.validate_capacity(Size.parse("48GiB"))


def test_capacity_rejects_unknown_size() -> None:
    with pytest.raises(ConfigError, match="unable to determine"):
        default_config().validate_capacity(Size(0))


def test_root_size_excludes_efi_and_swap() -> None:
    config = default_config()
    assert config.root_size_for(Size.parse("64GiB")) == Size.parse("31GiB")


# -- hibernation vs RAM -----------------------------------------------------


def test_hibernation_rejects_swap_smaller_than_ram() -> None:
    with pytest.raises(ConfigError, match="at least"):
        default_config().validate_hibernation(64 * 1024**3)


def test_hibernation_accepts_swap_at_least_ram() -> None:
    default_config().validate_hibernation(32 * 1024**3)


def test_hibernation_check_skipped_when_disabled() -> None:
    default_config(hibernation=False).validate_hibernation(1024 * 1024**3)


# -- encryption guards ------------------------------------------------------


def test_tpm2_requires_encryption() -> None:
    with pytest.raises(ValidationError):
        EncryptionConfig(enabled=False, tpm2_enabled=True)


def test_tpm2_requires_a_recovery_key() -> None:
    """A TPM2 seal breaks on firmware updates. Without a recovery key that is a
    lost machine, so the combination is refused rather than documented."""
    with pytest.raises(ValidationError, match="recovery"):
        EncryptionConfig(tpm2_enabled=True, recovery_key=False)


# -- system -----------------------------------------------------------------


@pytest.mark.parametrize("hostname", ["frame_work", "-framework", "Framework", "a" * 64])
def test_hostname_rejected(hostname: str) -> None:
    with pytest.raises(ValidationError):
        SystemConfig(hostname=hostname)


def test_kernels_deduplicated() -> None:
    assert SystemConfig(default_kernel="linux", fallback_kernel="linux").kernels == [
        "linux"
    ]


def test_mandatory_package_groups_always_present() -> None:
    from arch_framework.lib.models import MANDATORY_GROUPS, PackageConfig

    config = PackageConfig(groups=[])
    for group in MANDATORY_GROUPS:
        assert group in config.groups


# -- persistence ------------------------------------------------------------


def test_save_and_load_round_trip(tmp_path: Path) -> None:
    original = default_config()
    path = tmp_path / "config.json"
    original.save(path)
    assert InstallConfig.load(path).to_json() == original.to_json()


def test_serialisation_is_deterministic() -> None:
    """Two identical machines must produce byte-identical files, otherwise a
    saved configuration is useless as a reproducibility artefact."""
    assert default_config().to_json() == default_config().to_json()


def test_load_reports_missing_file(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="not found"):
        InstallConfig.load(tmp_path / "absent.json")


def test_load_reports_bad_json(tmp_path: Path) -> None:
    path = tmp_path / "broken.json"
    path.write_text("{ not json", encoding="utf-8")
    with pytest.raises(ConfigError, match="not valid JSON"):
        InstallConfig.load(path)


def test_passwords_never_appear_in_saved_config() -> None:
    """Credentials live in a separate file on purpose."""
    assert "password" not in default_config().to_json().lower()
