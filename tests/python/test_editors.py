"""Tests for the menu editors, driven through a scripted prompt backend.

The editors are where the constraint logic lives: which options are offered,
which are locked and why, and what the configuration looks like afterwards. They
used to be reachable only by typing at a real prompt, so nothing checked them.
With a backend that answers from a script, the real closures from build_menu()
run — which is also the property that lets a curses front-end reuse them instead
of carrying a second copy.
"""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from configurator import catalogue, prompts  # noqa: E402
from configurator.config import Configuration, Size  # noqa: E402
from configurator.menu import build_menu  # noqa: E402

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "devices.json"

GIB = 1024


class Exhausted(AssertionError):
    """The editor asked more questions than the test scripted."""


class ScriptedPrompts(prompts.Prompts):
    """Answers in order, and records everything it was asked.

    An answer of ``prompts.Abandoned`` (the class, not an instance) is raised
    instead of returned, which is how a test reproduces the user pressing escape
    part way through a multi-question editor.
    """

    def __init__(self, *answers: object) -> None:
        self.answers = list(answers)
        self.calls: list[dict] = []

    def _next(self, record: dict) -> object:
        self.calls.append(record)
        if not self.answers:
            raise Exhausted(f"unscripted question: {record}")
        answer = self.answers.pop(0)
        if answer is prompts.Abandoned:
            raise prompts.Abandoned
        return answer

    def text(self, label: str, current: str) -> str:
        answer = self._next({"kind": "text", "label": label, "current": current})
        return current if answer is None else str(answer)

    def boolean(self, label: str, current: bool) -> bool:
        answer = self._next({"kind": "boolean", "label": label, "current": current})
        return current if answer is None else bool(answer)

    def choice(self, label, options, current):  # type: ignore[no-untyped-def]
        answer = self._next(
            {
                "kind": "choice",
                "label": label,
                "options": list(options),
                "current": current,
            }
        )
        return current if answer is None else answer

    def checkboxes(self, label, options, selected, *, locked_on=()):  # type: ignore[no-untyped-def]
        answer = self._next(
            {
                "kind": "checkboxes",
                "label": label,
                "options": list(options),
                "selected": list(selected),
                "locked_on": tuple(locked_on),
            }
        )
        return list(selected) if answer is None else list(answer)

    # -- reading what was asked ----------------------------------------------

    def labels(self) -> list[str]:
        return [call["label"] for call in self.calls]

    def call(self, index: int) -> dict:
        return self.calls[index]

    def reason_for(self, index: int, value: object) -> str | None:
        for option_value, _, reason in self.calls[index]["options"]:
            if option_value == value:
                return reason
        raise AssertionError(f"{value!r} was not offered in call {index}")


def editor(key: str):
    """The real closure from build_menu(), by entry key."""
    entry = build_menu().get(key)
    assert entry is not None and entry.edit is not None, key
    return entry.edit


def run(key: str, config: Configuration, *answers: object):
    """Drive one editor with scripted answers. Returns (note, backend)."""
    backend = ScriptedPrompts(*answers)
    with prompts.using(backend):
        return editor(key)(config), backend


class EncryptionTests(unittest.TestCase):
    def test_turning_encryption_off_takes_tpm2_with_it(self) -> None:
        config = Configuration(luks_enabled=True, tpm2_enabled=True)
        note, backend = run("tpm2_enabled", config, False)

        self.assertFalse(config.luks_enabled)
        self.assertFalse(config.tpm2_enabled)
        self.assertIn("TPM2 disabled", note or "")
        # With nothing left to unlock, the TPM2 question is not asked at all.
        self.assertEqual([call["kind"] for call in backend.calls], ["boolean"])

    def test_tpm2_is_offered_when_encryption_stays_on(self) -> None:
        config = Configuration(luks_enabled=True, tpm2_enabled=False)
        run("tpm2_enabled", config, True, True)

        self.assertTrue(config.luks_enabled)
        self.assertTrue(config.tpm2_enabled)


class MemoryTests(unittest.TestCase):
    def test_hibernation_locks_the_sizes_that_cannot_hold_the_image(self) -> None:
        """The sizes are trialled with the @swap subvolume the same choice would
        create, so only genuinely-too-small sizes come back locked."""
        config = Configuration(
            memory_mib=32 * GIB, swap_size=Size(0), hibernation_enabled=False
        )
        note, backend = run("swap_size", config, True, True, Size(32 * GIB))

        swap_question = len(backend.calls) - 1
        self.assertIsNotNone(backend.reason_for(swap_question, Size(0)))
        self.assertIsNotNone(backend.reason_for(swap_question, Size(8 * GIB)))
        self.assertIsNone(backend.reason_for(swap_question, Size(32 * GIB)))

        self.assertTrue(config.hibernation_enabled)
        self.assertEqual(config.swap_size, Size(32 * GIB))
        self.assertIn("@swap", config.btrfs_subvolumes)
        self.assertIn("swap", (note or "").lower())

    def test_turning_hibernation_off_removes_the_swap_subvolume(self) -> None:
        config = Configuration(
            memory_mib=32 * GIB,
            swap_size=Size(32 * GIB),
            hibernation_enabled=True,
            btrfs_subvolumes=["@", "@home", "@swap"],
        )
        run("swap_size", config, True, False, Size(0))

        self.assertFalse(config.hibernation_enabled)
        self.assertEqual(config.swap_size, Size(0))
        self.assertNotIn("@swap", config.btrfs_subvolumes)


class SoftwareTests(unittest.TestCase):
    def test_the_unbootable_groups_are_locked_on(self) -> None:
        config = Configuration()
        backend = ScriptedPrompts(None)
        with prompts.using(backend):
            editor("package_groups")(config)

        self.assertEqual(
            set(backend.call(0)["locked_on"]), {"base", "firmware", "framework"}
        )

    def test_selecting_everything_is_recorded_as_the_default(self) -> None:
        """An explicit list of every group and an unset PACKAGE_GROUPS install the
        same thing, so the generated file stays quiet about it."""
        every_group = [group.name for group in catalogue.package_groups()]

        config = Configuration()
        note, _ = run("package_groups", config, every_group)

        self.assertEqual(note, "every group selected")
        self.assertEqual(config.package_groups, [])

    def test_deselecting_a_group_is_reported(self) -> None:
        config = Configuration()
        note, _ = run("package_groups", config, ["base", "firmware", "framework"])

        self.assertEqual(config.package_groups, ["base", "firmware", "framework"])
        self.assertIn("skipping:", note or "")

    def test_no_aur_software_is_a_real_choice(self) -> None:
        config = Configuration()
        note, _ = run("aur_packages", config, [])

        self.assertTrue(config.aur_selected)
        self.assertEqual(config.aur_packages, [])
        self.assertIn("afi-aur-setup", note or "")


class DiskTests(unittest.TestCase):
    def setUp(self) -> None:
        self._previous = os.environ.get("AFI_DEVICES_FIXTURE")
        os.environ["AFI_DEVICES_FIXTURE"] = str(FIXTURE)

    def tearDown(self) -> None:
        if self._previous is None:
            os.environ.pop("AFI_DEVICES_FIXTURE", None)
        else:
            os.environ["AFI_DEVICES_FIXTURE"] = self._previous

    def test_the_live_medium_is_offered_but_locked(self) -> None:
        """Hidden, the user wonders where their disk went; offered and refused,
        they learn that installing onto the stick they booted from is the reason."""
        config = Configuration()
        _, backend = run("target_disk", config, "/dev/nvme0n1")

        self.assertIsNone(backend.reason_for(0, "/dev/nvme0n1"))
        self.assertIsNotNone(backend.reason_for(0, "/dev/sdb"))

    def test_choosing_a_disk_records_its_size_and_counts_as_answered(self) -> None:
        config = Configuration()
        run("target_disk", config, "/dev/nvme0n1")

        self.assertEqual(config.target_disk, "/dev/nvme0n1")
        self.assertIn("target_disk", config.answered)
        self.assertGreater(config.disk_size_mib, 900 * GIB)


class IdentityAndLocaleTests(unittest.TestCase):
    def test_one_keyboard_choice_sets_console_and_graphical_layouts(self) -> None:
        """Setting only the keymap leaves the desktop on US QWERTY, which does not
        look like a keyboard configuration problem."""
        config = Configuration(keymap="us", xkb_layout="us", xkb_variant="")
        run(
            "locale",
            config,
            None,  # locale
            None,  # secondary locale
            ("fr_CH", "ch", "fr_nodeadkeys", "Swiss French"),
            None,  # timezone
        )

        self.assertEqual(config.keymap, "fr_CH")
        self.assertEqual(config.xkb_layout, "ch")
        self.assertEqual(config.xkb_variant, "fr_nodeadkeys")

    def test_abandoning_part_way_keeps_what_was_already_answered(self) -> None:
        """Today's behaviour, pinned deliberately: the editors commit as they go,
        so escape means "stop asking", not "undo"."""
        config = Configuration(hostname="framework", username="user")
        backend = ScriptedPrompts("laptop", prompts.Abandoned)
        with prompts.using(backend):
            with self.assertRaises(prompts.Abandoned):
                editor("username")(config)

        self.assertEqual(config.hostname, "laptop")
        self.assertEqual(config.username, "user")


class SingleProviderTests(unittest.TestCase):
    def test_the_only_bootloader_is_refused_rather_than_pretended(self) -> None:
        config = Configuration()
        with prompts.using(ScriptedPrompts()):
            with self.assertRaises(ValueError):
                editor("bootloader")(config)


if __name__ == "__main__":
    unittest.main()
