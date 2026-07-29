"""Tests for the configuration front-end.

Standard library only, run with ``python -m unittest discover``, because the ISO
ships Python without pytest and a test suite that cannot run there is a test
suite that stops being run.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from configurator import constraints  # noqa: E402
from configurator.config import Configuration, Size, parse_shell_config  # noqa: E402
from configurator.devices import Disk  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class SizeTests(unittest.TestCase):
    def test_parses_the_shell_format(self) -> None:
        self.assertEqual(Size.parse("32GiB").mib, 32768)
        self.assertEqual(Size.parse("0GiB").mib, 0)
        self.assertEqual(Size.parse("1024MiB").mib, 1024)

    def test_rejects_other_units(self) -> None:
        for text in ("32GB", "32 GiB", "GiB", "1.5GiB"):
            with self.subTest(text=text), self.assertRaises(ValueError):
                Size.parse(text)

    def test_round_trips_through_the_shell_format(self) -> None:
        for text in ("0GiB", "512MiB", "32GiB", "1TiB"):
            with self.subTest(text=text):
                self.assertEqual(str(Size.parse(text)), text)


class ShellParsingTests(unittest.TestCase):
    """The file is Bash, but it is parsed rather than executed: sourcing it would
    run whatever it contains."""

    def test_reads_scalars_and_arrays(self) -> None:
        values = parse_shell_config(
            """
# a comment
HOSTNAME="framework"
SWAP_SIZE="0GiB"
LUKS_ENABLED="true"
BTRFS_SUBVOLUMES=(
    "@"
    "@home"
)
"""
        )
        self.assertEqual(values["HOSTNAME"], "framework")
        self.assertEqual(values["SWAP_SIZE"], "0GiB")
        self.assertEqual(values["BTRFS_SUBVOLUMES"], ["@", "@home"])

    def test_ignores_trailing_comments(self) -> None:
        values = parse_shell_config('USERNAME="user" # the account\n')
        self.assertEqual(values["USERNAME"], "user")

    def test_reads_the_real_shipped_configuration(self) -> None:
        config = Configuration.load(PROJECT_ROOT / "config" / "system.conf")
        self.assertTrue(config.target_disk.startswith("/dev/"))
        self.assertIn("@", config.btrfs_subvolumes)
        self.assertTrue(config.luks_enabled)


class RoundTripTests(unittest.TestCase):
    def test_generated_file_reparses_identically(self) -> None:
        """The generated file is what install.sh sources, so it has to survive a
        round trip through the same parser."""
        original = Configuration.load(PROJECT_ROOT / "config" / "system.conf")
        original.swap_size = Size(32768)
        original.hibernation_enabled = True
        original.btrfs_subvolumes.append("@swap")

        reparsed = Configuration.from_shell(parse_shell_config(original.to_shell()))

        self.assertEqual(reparsed.swap_size, original.swap_size)
        self.assertTrue(reparsed.hibernation_enabled)
        self.assertIn("@swap", reparsed.btrfs_subvolumes)
        self.assertEqual(reparsed.target_disk, original.target_disk)

    def test_booleans_render_as_the_shell_expects(self) -> None:
        config = Configuration(luks_enabled=True, zram_enabled=False)
        rendered = config.to_shell()
        self.assertIn('LUKS_ENABLED="true"', rendered)
        self.assertIn('ZRAM_ENABLED="false"', rendered)
        self.assertNotIn("True", rendered)


class ConstraintTests(unittest.TestCase):
    def base(self, **overrides: object) -> Configuration:
        config = Configuration(target_disk="/dev/nvme0n1", memory_mib=32 * 1024)
        for name, value in overrides.items():
            setattr(config, name, value)
        config.answered.update({"target_disk", "username"})
        return config

    def keys(self, config: Configuration) -> set[str]:
        return {v.field for v in constraints.blocking(config)}

    def test_the_shipped_default_is_installable(self) -> None:
        self.assertTrue(constraints.is_installable(self.base()))

    def test_tpm2_without_luks_is_blocked(self) -> None:
        config = self.base(luks_enabled=False, tpm2_enabled=True)
        self.assertIn("tpm2_enabled", self.keys(config))

    def test_hibernation_without_swap_is_blocked(self) -> None:
        config = self.base(hibernation_enabled=True, swap_size=Size(0))
        self.assertIn("swap_size", self.keys(config))

    def test_swap_below_ram_is_blocked(self) -> None:
        config = self.base(
            hibernation_enabled=True,
            swap_size=Size(8 * 1024),
            btrfs_subvolumes=["@", "@home", "@snapshots", "@cache", "@log", "@swap"],
        )
        self.assertIn("swap_size", self.keys(config))

    def test_swapfile_without_the_subvolume_is_blocked(self) -> None:
        """Copy-on-write corrupts a swapfile, and the attribute can only be
        cleared while the subvolume is empty."""
        config = self.base(swap_size=Size(32 * 1024))
        self.assertIn("swap_size", self.keys(config))

    def test_a_coherent_hibernation_setup_passes(self) -> None:
        config = self.base(
            hibernation_enabled=True,
            swap_size=Size(32 * 1024),
            btrfs_subvolumes=["@", "@home", "@snapshots", "@cache", "@log", "@swap"],
        )
        self.assertTrue(constraints.is_installable(config), self.keys(config))

    def test_unknown_memory_disables_the_sizing_rule(self) -> None:
        """Zero means unknown. Comparing against a guess would be worse than not
        comparing at all."""
        config = self.base(
            memory_mib=0,
            hibernation_enabled=True,
            swap_size=Size(1024),
            btrfs_subvolumes=["@", "@home", "@snapshots", "@cache", "@log", "@swap"],
        )
        self.assertTrue(constraints.is_installable(config))

    def test_advisories_do_not_block(self) -> None:
        config = self.base(zram_enabled=False)
        self.assertTrue(constraints.is_installable(config))
        self.assertTrue(
            any(not v.blocking for v in constraints.evaluate(config))
        )

    def test_a_layout_that_starves_root_is_blocked(self) -> None:
        config = self.base(
            disk_size_mib=48 * 1024,
            swap_size=Size(32 * 1024),
            btrfs_subvolumes=["@", "@home", "@snapshots", "@cache", "@log", "@swap"],
        )
        self.assertIn("swap_size", self.keys(config))


class AvailabilityTests(unittest.TestCase):
    """The locking the menu displays. Values are trialled against the rules, so a
    new rule changes what is offered with no second place to update."""

    def config(self, **overrides: object) -> Configuration:
        config = Configuration(
            target_disk="/dev/nvme0n1",
            memory_mib=32 * 1024,
            btrfs_subvolumes=["@", "@home", "@snapshots", "@cache", "@log", "@swap"],
        )
        for name, value in overrides.items():
            setattr(config, name, value)
        config.answered.update({"target_disk", "username"})
        return config

    def test_hibernation_locks_zero_swap(self) -> None:
        config = self.config(hibernation_enabled=True, swap_size=Size(32 * 1024))
        result = constraints.availability(
            config, "swap_size", [Size(0), Size(32 * 1024)]
        )

        self.assertIn(Size(32 * 1024), result.allowed)
        self.assertIsNotNone(result.reason_for(Size(0)))
        self.assertIn("zram is cleared", result.reason_for(Size(0)))

    def test_hibernation_locks_sizes_below_ram(self) -> None:
        config = self.config(hibernation_enabled=True, swap_size=Size(32 * 1024))
        result = constraints.availability(
            config, "swap_size", [Size(8 * 1024), Size(32 * 1024)]
        )

        self.assertIsNotNone(result.reason_for(Size(8 * 1024)))
        self.assertIn(Size(32 * 1024), result.allowed)

    def test_without_hibernation_every_swap_size_is_offered(self) -> None:
        config = self.config(hibernation_enabled=False)
        result = constraints.availability(
            config,
            "swap_size",
            [Size(0), Size(8 * 1024), Size(32 * 1024)],
            apply=lambda c, v: c.with_swap_size(v),
        )
        self.assertEqual(result.locked, [])

    def test_choosing_a_size_is_not_blocked_by_the_subvolume_it_creates(self) -> None:
        """Selecting a swap size is what adds @swap. Locking sizes because @swap
        is absent would block a choice for one of its own consequences."""
        config = self.config(
            hibernation_enabled=False,
            btrfs_subvolumes=["@", "@home", "@snapshots", "@cache", "@log"],
        )
        result = constraints.availability(
            config,
            "swap_size",
            [Size(32 * 1024)],
            apply=lambda c, v: c.with_swap_size(v),
        )
        self.assertEqual(result.locked, [])
        self.assertIn(Size(32 * 1024), result.allowed)

    def test_trialling_does_not_mutate_the_real_configuration(self) -> None:
        """dataclasses.replace shares mutable members, so a trial could otherwise
        edit the live subvolume list."""
        config = self.config(
            btrfs_subvolumes=["@", "@home", "@snapshots", "@cache", "@log"]
        )
        before = list(config.btrfs_subvolumes)

        constraints.availability(
            config,
            "swap_size",
            [Size(32 * 1024), Size(0)],
            apply=lambda c, v: c.with_swap_size(v),
        )

        self.assertEqual(config.btrfs_subvolumes, before)

    def test_applying_a_size_adds_and_removes_the_subvolume(self) -> None:
        config = self.config(
            btrfs_subvolumes=["@", "@home", "@snapshots", "@cache", "@log"]
        )
        note = config.apply_swap_size(Size(32 * 1024))
        self.assertIn("@swap", config.btrfs_subvolumes)
        self.assertIsNotNone(note)

        note = config.apply_swap_size(Size(0))
        self.assertNotIn("@swap", config.btrfs_subvolumes)
        self.assertIsNotNone(note)

    def test_tpm2_is_locked_without_encryption(self) -> None:
        config = self.config(luks_enabled=False, tpm2_enabled=False)
        result = constraints.availability(config, "tpm2_enabled", [True, False])

        self.assertIn(False, result.allowed)
        self.assertIsNotNone(result.reason_for(True))


class HibernationToggleTests(unittest.TestCase):
    def test_enabling_brings_the_layout_with_it(self) -> None:
        """Making the user discover the requirement by being blocked would be a
        poor way to guide them."""
        config = Configuration(memory_mib=16 * 1024, swap_size=Size(0))
        note = config.set_hibernation(True)

        self.assertTrue(config.hibernation_enabled)
        self.assertIn("@swap", config.btrfs_subvolumes)
        self.assertGreaterEqual(config.swap_size.mib, config.memory_mib)
        self.assertIsNotNone(note)

    def test_disabling_removes_what_it_added(self) -> None:
        config = Configuration(memory_mib=16 * 1024)
        config.set_hibernation(True)
        config.set_hibernation(False)

        self.assertFalse(config.hibernation_enabled)
        self.assertNotIn("@swap", config.btrfs_subvolumes)
        self.assertEqual(config.swap_size.mib, 0)

    def test_the_result_is_installable(self) -> None:
        config = Configuration(target_disk="/dev/nvme0n1", memory_mib=16 * 1024)
        config.answered.update({"target_disk", "username"})
        config.set_hibernation(True)
        self.assertTrue(
            constraints.is_installable(config),
            {v.field: v.message for v in constraints.blocking(config)},
        )

    def test_turning_encryption_off_turns_tpm2_off(self) -> None:
        config = Configuration(luks_enabled=True, tpm2_enabled=True)
        note = config.set_encryption(False)

        self.assertFalse(config.tpm2_enabled)
        self.assertIsNotNone(note)


class DiskTests(unittest.TestCase):
    """Ineligible disks are shown with a reason rather than hidden: a disk that
    silently does not appear leaves the user guessing."""

    def test_the_live_medium_is_rejected(self) -> None:
        disk = Disk("/dev/sdb", "Ultra Fit", 30000, "usb", True, True, [])
        self.assertFalse(disk.eligible)
        self.assertEqual(disk.rejection, "Arch live medium")
        self.assertIn("Rejected", disk.describe())

    def test_usb_is_rejected(self) -> None:
        disk = Disk("/dev/sdc", "Stick", 30000, "usb", False, False, [])
        self.assertEqual(disk.rejection, "USB transport")

    def test_removable_is_rejected(self) -> None:
        disk = Disk("/dev/mmcblk0", "Card", 30000, "mmc", True, False, [])
        self.assertEqual(disk.rejection, "removable device")

    def test_an_internal_disk_is_eligible(self) -> None:
        disk = Disk("/dev/nvme0n1", "SN770", 950000, "nvme", False, False, [])
        self.assertTrue(disk.eligible)
        self.assertIsNone(disk.rejection)

    def test_a_mounted_disk_is_eligible_with_a_warning(self) -> None:
        disk = Disk("/dev/nvme0n1", "SN770", 950000, "nvme", False, False, ["/mnt"])
        self.assertTrue(disk.eligible)
        self.assertIn("Warning", disk.describe())


if __name__ == "__main__":
    unittest.main()
