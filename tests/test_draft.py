from __future__ import annotations

import pytest

from arch_framework.lib.models.device import SWAP_SUBVOLUME
from arch_framework.profiles import default_config
from arch_framework.tui.draft import Draft


def test_valid_edit_is_applied() -> None:
    draft = Draft(default_config())
    draft.update(lambda payload: payload["system"].update(hostname="laptop"))
    assert draft.config.system.hostname == "laptop"


def test_rejected_edit_changes_nothing() -> None:
    """A half-applied edit would either bypass the cross-field rules or leave an
    invalid document behind."""
    draft = Draft(default_config())
    before = draft.config.to_json()

    with pytest.raises(ValueError):
        draft.update(lambda payload: payload["system"].update(hostname="Bad_Name"))

    assert draft.config.to_json() == before


def test_rejection_message_is_readable() -> None:
    draft = Draft(default_config())
    with pytest.raises(ValueError, match="efi_size"):
        draft.update(lambda payload: payload["disk"].update(efi_size="16MiB"))


def test_cross_field_rule_still_fires() -> None:
    draft = Draft(default_config())
    with pytest.raises(ValueError, match="@swap"):
        draft.update(
            lambda payload: payload["disk"].update(
                subvolumes=["@", "@home", "@snapshots", "@cache", "@log"]
            )
        )


# -- hibernation ------------------------------------------------------------


def test_enabling_hibernation_adds_the_swap_subvolume() -> None:
    """Making the user discover the requirement by being rejected would be a
    poor way to guide them."""
    draft = Draft(default_config(hibernation=False))
    assert SWAP_SUBVOLUME not in draft.config.disk.subvolumes

    note = draft.set_hibernation(True)

    assert draft.config.swap.hibernation_enabled
    assert SWAP_SUBVOLUME in draft.config.disk.subvolumes
    assert note is not None and SWAP_SUBVOLUME in note


def test_disabling_hibernation_removes_the_swap_subvolume() -> None:
    draft = Draft(default_config(hibernation=True))
    note = draft.set_hibernation(False)

    assert not draft.config.swap.hibernation_enabled
    assert SWAP_SUBVOLUME not in draft.config.disk.subvolumes
    assert note is not None


def test_toggling_hibernation_is_silent_when_nothing_changes() -> None:
    draft = Draft(default_config(hibernation=True))
    assert draft.set_hibernation(True) is None


def test_hibernation_round_trip_restores_the_subvolume_set() -> None:
    draft = Draft(default_config(hibernation=True))
    original = list(draft.config.disk.subvolumes)
    draft.set_hibernation(False)
    draft.set_hibernation(True)
    assert draft.config.disk.subvolumes == original


# -- answered tracking ------------------------------------------------------


def test_nothing_is_answered_initially() -> None:
    """The profile supplies a placeholder disk so the document is well-formed.
    Without tracking answers, a placeholder is indistinguishable from a choice."""
    assert Draft(default_config()).answered == frozenset()


def test_marking_an_answer() -> None:
    draft = Draft(default_config())
    draft.mark_answered("disk")
    assert draft.is_answered("disk")
    assert not draft.is_answered("users")


def test_a_saved_configuration_counts_as_fully_answered() -> None:
    """Replaying a saved configuration unchanged is the reproducibility path.
    Gating it behind walking the menu again would defeat the purpose."""
    draft = Draft.from_saved(default_config(), ["disk", "users"])
    assert draft.is_answered("disk")
    assert draft.is_answered("users")
