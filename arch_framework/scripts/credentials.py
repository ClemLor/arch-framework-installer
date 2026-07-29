"""Collecting secrets.

Kept out of the configuration document entirely. The saved configuration is meant
to be readable, reviewable and reusable across rebuilds; a password in it would
make it a file that cannot be shared or committed, which would undermine the one
artefact this project depends on.

Secrets come from a credentials file when one is given, and are prompted for
otherwise. They are never written anywhere by this code.
"""

from __future__ import annotations

from pathlib import Path

from ..lib import log
from ..lib.exceptions import StageError
from ..lib.models import Credentials, InstallConfig
from ..tui.prompt import ask_password


def collect(
    config: InstallConfig,
    *,
    path: Path | None = None,
    interactive: bool = True,
) -> Credentials:
    credentials = Credentials.load(path) if path is not None else Credentials()

    if config.encryption.enabled and not credentials.encryption_passphrase:
        if not interactive:
            raise StageError(
                "encryption is enabled but no passphrase was supplied and there "
                "is no terminal to ask on; provide one with --creds"
            )
        log.section("Disk encryption")
        log.info(
            "This passphrase is asked for at every boot until the TPM2 takes "
            "over, and remains the way in if the TPM2 stops working."
        )
        credentials.encryption_passphrase = ask_password("LUKS passphrase")

    missing = credentials.missing_for(config.users)
    if missing:
        if not interactive:
            raise StageError(
                f"no password supplied for: {', '.join(missing)}; provide them "
                "with --creds"
            )
        log.section("Account passwords")
        for name in missing:
            password = ask_password(f"Password for {name}")
            if name == "root":
                credentials.root_password = password
            else:
                credentials.user_passwords[name] = password

    return credentials
