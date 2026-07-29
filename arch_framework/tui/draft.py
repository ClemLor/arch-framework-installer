"""A configuration being edited.

Menu entries cannot mutate an :class:`InstallConfig` field by field: the model
carries cross-field rules — hibernation requires ``@swap``, TPM2 requires a
recovery key — and a half-applied edit would either bypass them or leave the
object invalid. So edits go through :meth:`Draft.update`, which mutates a plain
payload, revalidates the whole document, and reverts if the result is rejected.

The draft also records which entries the user has actually answered. That
matters for the target disk: the profile supplies a placeholder so the rest of
the configuration is well-formed, and without tracking answers a placeholder
would be indistinguishable from a decision. Nothing is installed onto a disk
nobody chose.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Any

from pydantic import ValidationError

from ..lib.models import InstallConfig


def _readable(error: ValidationError) -> str:
    """Turn a pydantic error into one line a person can act on."""
    messages: list[str] = []
    for item in error.errors():
        location = ".".join(str(part) for part in item["loc"]) or "configuration"
        message = item["msg"].removeprefix("Value error, ")
        messages.append(f"{location}: {message}")
    return "; ".join(dict.fromkeys(messages))


class Draft:
    def __init__(
        self,
        config: InstallConfig,
        *,
        answered: frozenset[str] | None = None,
    ) -> None:
        self._config = config
        self._answered: set[str] = set(answered or ())

    @classmethod
    def from_saved(cls, config: InstallConfig, keys: Iterable[str]) -> "Draft":
        """A draft loaded from a file the user previously saved.

        Every entry counts as answered. The unanswered state exists to stop the
        profile's placeholder disk from being installed onto by default, not to
        make someone re-answer decisions they already made — replaying a saved
        configuration unchanged is the reproducibility path this project exists
        for, and it must not be gated behind walking the menu again.
        """
        return cls(config, answered=frozenset(keys))

    @property
    def config(self) -> InstallConfig:
        return self._config

    # -- answers ------------------------------------------------------------

    def mark_answered(self, key: str) -> None:
        self._answered.add(key)

    def is_answered(self, key: str) -> bool:
        return key in self._answered

    @property
    def answered(self) -> frozenset[str]:
        return frozenset(self._answered)

    # -- edits --------------------------------------------------------------

    def payload(self) -> dict[str, Any]:
        return self._config.model_dump(mode="json")

    def update(self, mutate: Callable[[dict[str, Any]], None]) -> None:
        """Apply an edit, or raise ValueError and change nothing.

        Renderers catch ValueError and show the message, so a rejected edit is a
        readable refusal rather than a traceback or a corrupted draft.
        """
        payload = self.payload()
        mutate(payload)

        try:
            self._config = InstallConfig.model_validate(payload)
        except ValidationError as exc:
            raise ValueError(_readable(exc)) from exc

    def set_hibernation(self, enabled: bool) -> str | None:
        """Toggle hibernation, adjusting the subvolume set to match.

        Enabling hibernation without ``@swap`` is invalid, and making the user
        discover that by being rejected would be a poor way to guide them. The
        subvolume is added or removed here, and what happened is reported so the
        change is not silent.
        """
        from ..lib.models.device import SWAP_SUBVOLUME

        note: str | None = None

        def mutate(payload: dict[str, Any]) -> None:
            nonlocal note
            payload["swap"]["hibernation_enabled"] = enabled
            subvolumes: list[str] = payload["disk"]["subvolumes"]

            if enabled and SWAP_SUBVOLUME not in subvolumes:
                subvolumes.append(SWAP_SUBVOLUME)
                note = (
                    f"Added the {SWAP_SUBVOLUME} subvolume: a swapfile needs "
                    "copy-on-write disabled and must be excluded from snapshots."
                )
            elif not enabled and SWAP_SUBVOLUME in subvolumes:
                subvolumes.remove(SWAP_SUBVOLUME)
                note = f"Removed the now-unused {SWAP_SUBVOLUME} subvolume."

        self.update(mutate)
        return note
