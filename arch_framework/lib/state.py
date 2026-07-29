"""Which stages have completed.

An installation that fails at the bootloader should not require repartitioning to
retry. State lives on the live medium's tmpfs rather than in the target, because
the target may not be mounted when it needs to be read.

The state records the configuration it belongs to. Resuming with a different
configuration is refused: half a system built to one layout and half to another
is worse than starting again.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path

from . import log
from .exceptions import StageError
from .models import InstallConfig

DEFAULT_STATE_PATH = Path("/run/arch-framework-installer.state.json")


def fingerprint(config: InstallConfig) -> str:
    """Identifies the configuration. Serialisation is deterministic, so this is
    stable across runs of the same document."""
    return hashlib.sha256(config.to_json().encode("utf-8")).hexdigest()[:16]


@dataclass
class InstallState:
    path: Path = DEFAULT_STATE_PATH
    config_fingerprint: str = ""
    completed: list[str] = field(default_factory=list)

    @classmethod
    def load_or_new(cls, config: InstallConfig, path: Path | None = None) -> "InstallState":
        path = path or DEFAULT_STATE_PATH
        current = fingerprint(config)

        if not path.is_file():
            return cls(path=path, config_fingerprint=current)

        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            log.warn(f"{path} could not be read; starting from the first stage.")
            return cls(path=path, config_fingerprint=current)

        saved = payload.get("config_fingerprint", "")
        if saved != current:
            raise StageError(
                f"{path} belongs to a different configuration. Delete it to start "
                "again, or resume with the configuration it was created from — "
                "building half a system to each layout is worse than restarting."
            )

        state = cls(
            path=path,
            config_fingerprint=saved,
            completed=list(payload.get("completed") or []),
        )
        if state.completed:
            log.info(f"Resuming: {len(state.completed)} stage(s) already done.")
        return state

    def is_done(self, stage: str) -> bool:
        return stage in self.completed

    def mark_done(self, stage: str) -> None:
        if stage not in self.completed:
            self.completed.append(stage)
        self.save()

    def save(self) -> None:
        payload = {
            "config_fingerprint": self.config_fingerprint,
            "completed": self.completed,
        }
        try:
            self.path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        except OSError as exc:
            # Not fatal: losing resumability is worse than nothing, but it is not
            # worth aborting a working installation over.
            log.warn(f"Could not record progress to {self.path}: {exc}")

    def clear(self) -> None:
        self.completed = []
        self.path.unlink(missing_ok=True)
