"""Tests for the software catalogue and the checkbox selection.

The catalogue reads the repository rather than carrying its own copy of the
lists, so these tests are partly about that: a package or a provider added on the
shell side must appear in the menu without the menu being edited.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from configurator import catalogue  # noqa: E402
from configurator.config import Configuration, parse_shell_config  # noqa: E402
from configurator.menu import ask_checkboxes  # noqa: E402


class Answers:
    """Feeds a scripted sequence to input()."""

    def __init__(self, *values: str) -> None:
        self.values = iter(values)

    def __call__(self, *_: object) -> str:
        return next(self.values)


def checkboxes(answers: Answers, *args: object, **kwargs: object) -> list[object]:
    """Drive ask_checkboxes with scripted input and swallow what it draws.

    Without the redirect the menu's own output buries the test results, which is
    how a real failure went unnoticed a moment ago.
    """
    import builtins
    import contextlib
    import io

    original = builtins.input
    builtins.input = answers
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            return ask_checkboxes(*args, **kwargs)  # type: ignore[arg-type]
    finally:
        builtins.input = original


class CatalogueTests(unittest.TestCase):
    def test_groups_come_from_the_shell_not_a_second_list(self) -> None:
        """AVAILABLE_PACKAGE_GROUPS is parsed out of lib/pacstraps.sh, so the two
        cannot disagree about which groups exist."""
        names = [group.name for group in catalogue.package_groups()]
        self.assertIn("base", names)
        self.assertIn("desktop", names)
        self.assertIn("optional", names)
        self.assertNotIn("aur", names)

    def test_mandatory_groups_are_marked(self) -> None:
        groups = {group.name: group for group in catalogue.package_groups()}
        self.assertTrue(groups["base"].mandatory)
        self.assertTrue(groups["firmware"].mandatory)
        self.assertTrue(groups["framework"].mandatory)
        self.assertFalse(groups["optional"].mandatory)

    def test_group_descriptions_report_size(self) -> None:
        groups = {group.name: group for group in catalogue.package_groups()}
        self.assertIn("package", groups["base"].description)

    def test_empty_groups_are_described_as_empty(self) -> None:
        """Selecting a group and getting nothing should be visible."""
        group = catalogue.Group(name="ghost", packages=[], mandatory=False)
        self.assertIn("empty", group.description)

    def test_aur_packages_are_read_with_their_descriptions(self) -> None:
        packages = {entry.name: entry for entry in catalogue.aur_packages()}
        self.assertIn("librewolf-bin", packages)
        self.assertIn("visual-studio-code-bin", packages)
        self.assertIn("cursor-bin", packages)
        # paru installs the list, so it must not be in it.
        self.assertNotIn("paru", packages)
        self.assertIn("telemetry", packages["librewolf-bin"].description)

    def test_standalone_comments_are_not_used_as_descriptions(self) -> None:
        """Only the package's own trailing comment counts. Guessing which
        standalone comment was meant produced "librewolf-bin — Browsers"."""
        packages = {entry.name: entry for entry in catalogue.aur_packages()}
        self.assertNotIn("Browsers", packages["librewolf-bin"].description)
        self.assertNotIn("Editors", packages["cursor-bin"].description)

    def test_a_package_without_a_comment_is_just_its_name(self) -> None:
        self.assertEqual(catalogue.AurPackage(name="foo").description, "foo")

    def test_supported_names_come_from_provider_module(self) -> None:
        """Adding a bootloader means listing it once in lib/provider.sh; it then
        appears in the menu with no Python change."""
        self.assertEqual(catalogue.supported("bootloaders"), ["limine"])
        self.assertEqual(catalogue.supported("compositors"), ["niri"])
        self.assertEqual(catalogue.supported("shells"), ["dank"])

    def test_unknown_kind_is_empty_not_an_error(self) -> None:
        self.assertEqual(catalogue.supported("nonexistent"), [])


class CheckboxTests(unittest.TestCase):
    def options(self):
        return [
            ("base", "base", None),
            ("desktop", "desktop", None),
            ("fonts", "fonts", None),
        ]

    def test_accepting_immediately_keeps_the_current_selection(self) -> None:
        chosen = checkboxes(Answers(""), "Groups", self.options(), ["base", "fonts"])
        self.assertEqual(chosen, ["base", "fonts"])

    def test_toggling_adds_and_removes(self) -> None:
        self.assertEqual(
            checkboxes(Answers("2", ""), "Groups", self.options(), ["base"]),
            ["base", "desktop"],
        )
        self.assertEqual(
            checkboxes(Answers("1", ""), "Groups", self.options(), ["base"]), []
        )

    def test_result_follows_the_display_order(self) -> None:
        """Not selection order: the generated file must be stable so two identical
        machines produce identical configuration."""
        self.assertEqual(
            checkboxes(Answers("3", "2", ""), "Groups", self.options(), ["base"]),
            ["base", "desktop", "fonts"],
        )

    def test_select_all_and_none(self) -> None:
        self.assertEqual(
            checkboxes(Answers("a", ""), "Groups", self.options(), []),
            ["base", "desktop", "fonts"],
        )
        self.assertEqual(
            checkboxes(Answers("n", ""), "Groups", self.options(), ["base"]), []
        )

    def test_locked_on_values_cannot_be_removed(self) -> None:
        """base, firmware and framework are shown permanently ticked rather than
        hidden, so the set stays visible."""
        chosen = checkboxes(
            Answers("1", ""), "Groups", self.options(), ["base"], locked_on=["base"]
        )
        self.assertIn("base", chosen)

    def test_locked_on_values_are_added_when_missing(self) -> None:
        chosen = checkboxes(
            Answers(""), "Groups", self.options(), ["fonts"], locked_on=["base"]
        )
        self.assertEqual(chosen, ["base", "fonts"])

    def test_unavailable_options_cannot_be_selected(self) -> None:
        options = [("base", "base", None), ("broken", "broken", "not implemented")]
        self.assertEqual(
            checkboxes(Answers("2", ""), "Groups", options, ["base"]), ["base"]
        )

    def test_nonsense_reprompts(self) -> None:
        self.assertEqual(
            checkboxes(Answers("zzz", "99", "2", ""), "Groups", self.options(), []),
            ["desktop"],
        )


class SelectionSerialisationTests(unittest.TestCase):
    """What the shell actually reads."""

    def base(self) -> Configuration:
        return Configuration.load(
            Path(__file__).resolve().parents[2] / "config" / "system.conf"
        )

    def test_full_selection_omits_the_variable(self) -> None:
        """An unset PACKAGE_GROUPS means every group to the shell, so writing the
        complete list out would be noise that could later drift."""
        config = self.base()
        config.package_groups = []
        rendered = config.to_shell()
        self.assertNotIn("PACKAGE_GROUPS", rendered)

    def test_partial_selection_is_written_as_an_array(self) -> None:
        config = self.base()
        config.package_groups = ["base", "firmware", "framework", "desktop"]
        values = parse_shell_config(config.to_shell())
        self.assertEqual(
            values["PACKAGE_GROUPS"], ["base", "firmware", "framework", "desktop"]
        )

    def test_unselected_aur_omits_the_variable(self) -> None:
        config = self.base()
        config.aur_selected = False
        self.assertNotIn("AUR_PACKAGES", config.to_shell())

    def test_an_empty_aur_selection_is_written_explicitly(self) -> None:
        """Deselecting everything is a real choice and must not be mistaken for
        never having chosen, which the shell reads as "install the whole list"."""
        config = self.base()
        config.aur_selected = True
        config.aur_packages = []
        rendered = config.to_shell()
        self.assertIn("AUR_PACKAGES=(", rendered)
        self.assertEqual(parse_shell_config(rendered)["AUR_PACKAGES"], [])

    def test_aur_selection_round_trips(self) -> None:
        config = self.base()
        config.aur_selected = True
        config.aur_packages = ["librewolf-bin", "cursor-bin"]
        reparsed = Configuration.from_shell(parse_shell_config(config.to_shell()))
        self.assertEqual(reparsed.aur_packages, ["librewolf-bin", "cursor-bin"])
        self.assertTrue(reparsed.aur_selected)

    def test_swappable_components_round_trip(self) -> None:
        config = self.base()
        values = parse_shell_config(config.to_shell())
        self.assertEqual(values["BOOTLOADER"], "limine")
        self.assertEqual(values["DESKTOP_COMPOSITOR"], "niri")
        self.assertEqual(values["DESKTOP_SHELL"], "dank")


if __name__ == "__main__":
    unittest.main()
