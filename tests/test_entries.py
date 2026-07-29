"""Tests for the menu entries, driven through the plain renderer.

These are the closest thing to an end-to-end test that can run without a live
ISO: a scripted sequence of keystrokes walks the real menu, edits the real
configuration, and the result is asserted.
"""

from __future__ import annotations

import pytest

from arch_framework.lib.disk import DeviceHandler, FixtureSource
from arch_framework.lib.models.device import SWAP_SUBVOLUME
from arch_framework.profiles import default_config
from arch_framework.tui.draft import Draft
from arch_framework.tui.entries import build_registry
from arch_framework.tui.menu import NOT_SET, Action
from arch_framework.tui.plain import PlainRenderer


@pytest.fixture
def setup(framework_source: FixtureSource):
    draft = Draft(default_config())
    registry = build_registry(draft, DeviceHandler(framework_source))
    return draft, registry


def drive(monkeypatch, registry, draft, *keys: str) -> Action:
    stream = iter(keys)
    monkeypatch.setattr("builtins.input", lambda *_: next(stream))
    return PlainRenderer(registry).run(draft)


def entry_number(registry, key: str) -> str:
    return str([e.key for e in registry.entries].index(key) + 1)


# -- structure --------------------------------------------------------------


def test_menu_covers_what_this_project_varies(setup) -> None:
    _, registry = setup
    assert [entry.key for entry in registry.entries] == [
        "locale",
        "timezone",
        "disk",
        "encryption",
        "swap",
        "kernels",
        "hostname",
        "users",
        "packages",
        "bootloader",
    ]


def test_mandatory_entries_are_the_destructive_and_unrecoverable_ones(setup) -> None:
    _, registry = setup
    mandatory = {entry.key for entry in registry.entries if entry.mandatory}
    assert mandatory == {"disk", "kernels", "users"}


def test_bootloader_is_shown_but_not_editable(setup) -> None:
    """One supported option. A menu with a single entry would imply otherwise."""
    _, registry = setup
    assert registry.get("bootloader").edit is None


def test_disk_and_users_start_unanswered(setup) -> None:
    draft, registry = setup
    assert registry.get("disk").preview(draft) == NOT_SET
    assert registry.get("users").preview(draft) == NOT_SET


def test_install_is_blocked_until_the_mandatory_entries_are_answered(setup) -> None:
    draft, registry = setup
    unanswered = {entry.key for entry in registry.unanswered_mandatory(draft)}
    assert unanswered == {"disk", "users"}


# -- disk -------------------------------------------------------------------


def test_choosing_the_disk_marks_it_answered(monkeypatch, setup) -> None:
    draft, registry = setup
    action = drive(
        monkeypatch,
        registry,
        draft,
        entry_number(registry, "disk"),
        "1",  # first (and only eligible) disk
        "",  # keep the EFI size
        "q",
    )
    assert action is Action.ABORT
    assert draft.is_answered("disk")
    assert draft.config.disk.target_disk == "/dev/nvme0n1"


def test_the_live_medium_cannot_be_chosen(monkeypatch, setup) -> None:
    """The guard is enforced in the menu, not only at install time."""
    draft, registry = setup
    drive(
        monkeypatch,
        registry,
        draft,
        entry_number(registry, "disk"),
        "2",  # the USB live medium — refused, reprompts
        "1",
        "",
        "q",
    )
    assert draft.config.disk.target_disk == "/dev/nvme0n1"


def test_disk_entry_reports_when_no_disks_exist(monkeypatch) -> None:
    draft = Draft(default_config())
    registry = build_registry(draft, DeviceHandler(FixtureSource({})))
    # A rejected edit must leave the menu usable rather than crash it.
    action = drive(monkeypatch, registry, draft, entry_number(registry, "disk"), "q")
    assert action is Action.ABORT
    assert not draft.is_answered("disk")


# -- swap and hibernation ---------------------------------------------------

def test_disabling_hibernation_drops_the_swap_subvolume(monkeypatch, setup) -> None:
    draft, registry = setup
    assert SWAP_SUBVOLUME in draft.config.disk.subvolumes

    drive(
        monkeypatch,
        registry,
        draft,
        entry_number(registry, "swap"),
        "",   # keep the size
        "",   # keep zram
        "n",  # no hibernation
        "q",
    )
    assert not draft.config.swap.hibernation_enabled
    assert SWAP_SUBVOLUME not in draft.config.disk.subvolumes


def test_a_swap_size_below_ram_is_still_accepted_by_the_menu(monkeypatch, setup) -> None:
    """The menu does not refuse it: the configuration may be written for a
    different machine. guided.run warns against the observed RAM instead."""
    draft, registry = setup
    drive(
        monkeypatch,
        registry,
        draft,
        entry_number(registry, "swap"),
        "8GiB",
        "",
        "",
        "q",
    )
    assert str(draft.config.swap.size) == "8GiB"


# -- encryption -------------------------------------------------------------


def test_turning_encryption_off_also_turns_off_tpm2(monkeypatch, setup) -> None:
    """TPM2 without LUKS is meaningless and the model rejects it, so the entry
    cannot leave that combination behind."""
    draft, registry = setup
    drive(
        monkeypatch,
        registry,
        draft,
        entry_number(registry, "encryption"),
        "n",
        "q",
    )
    assert not draft.config.encryption.enabled
    assert not draft.config.encryption.tpm2_enabled


def test_a_recovery_key_is_always_kept(monkeypatch, setup) -> None:
    draft, registry = setup
    drive(
        monkeypatch,
        registry,
        draft,
        entry_number(registry, "encryption"),
        "y",
        "y",
        "q",
    )
    assert draft.config.encryption.tpm2_enabled
    assert draft.config.encryption.recovery_key


# -- kernels ----------------------------------------------------------------


def test_first_kernel_becomes_default_second_becomes_fallback(monkeypatch, setup) -> None:
    draft, registry = setup
    drive(
        monkeypatch,
        registry,
        draft,
        entry_number(registry, "kernels"),
        "",  # accept linux-lts + linux as pre-selected
        "q",
    )
    assert draft.config.system.default_kernel == "linux-lts"
    assert draft.config.system.fallback_kernel == "linux"


def test_a_single_kernel_leaves_no_fallback(monkeypatch, setup) -> None:
    draft, registry = setup
    drive(
        monkeypatch,
        registry,
        draft,
        entry_number(registry, "kernels"),
        "2",  # deselect linux
        "",
        "q",
    )
    assert draft.config.system.kernels == ["linux-lts"]
    assert draft.config.system.fallback_kernel is None


# -- users ------------------------------------------------------------------


def test_creating_a_user_disables_root_login(monkeypatch, setup) -> None:
    """With a sudo user in place, a loginable root is a second password to
    protect for no gain."""
    draft, registry = setup
    drive(
        monkeypatch,
        registry,
        draft,
        entry_number(registry, "users"),
        "clement",
        "y",
        "",
        "q",
    )
    assert draft.config.users.users[0].name == "clement"
    assert draft.config.users.users[0].sudo
    assert not draft.config.users.root_login_enabled
    assert draft.is_answered("users")


def test_an_invalid_username_is_refused_without_breaking_the_menu(
    monkeypatch, setup
) -> None:
    draft, registry = setup
    action = drive(
        monkeypatch,
        registry,
        draft,
        entry_number(registry, "users"),
        "Bad Name",
        "y",
        "",
        "q",
    )
    assert action is Action.ABORT
    assert draft.config.users.users == []


# -- packages ---------------------------------------------------------------


def test_mandatory_package_groups_cannot_be_removed(monkeypatch, setup) -> None:
    draft, registry = setup
    drive(
        monkeypatch,
        registry,
        draft,
        entry_number(registry, "packages"),
        "1",  # try to drop base
        "",
        "q",
    )
    assert "base" in [group.value for group in draft.config.packages.groups]


# -- full walk --------------------------------------------------------------


def test_answering_everything_permits_install(monkeypatch, setup) -> None:
    draft, registry = setup
    action = drive(
        monkeypatch,
        registry,
        draft,
        entry_number(registry, "disk"), "1", "",
        entry_number(registry, "users"), "clement", "y", "",
        "i",
    )
    assert action is Action.INSTALL
    assert registry.unanswered_mandatory(draft) == []


def test_saving_is_permitted_at_any_point(setup, monkeypatch) -> None:
    """A saved configuration is the reproducibility artefact, so saving is never
    gated behind completing the menu."""
    draft, registry = setup
    assert drive(monkeypatch, registry, draft, "s") is Action.SAVE
