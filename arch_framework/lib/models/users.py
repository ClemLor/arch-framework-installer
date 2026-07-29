"""User accounts.

Passwords never live in the same document as the rest of the configuration:
the saved JSON is meant to be readable, committable and reusable, which a
password hash is not. Secrets go to a separate credentials file, mirroring
archinstall's ``--config`` / ``--creds`` split.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class User(BaseModel):
    name: str = Field(pattern=r"^[a-z_][a-z0-9_-]{0,31}$")
    sudo: bool = True
    shell: str = "/usr/bin/fish"
    groups: list[str] = Field(default_factory=list)

    @property
    def effective_groups(self) -> list[str]:
        groups = list(self.groups)
        if self.sudo and "wheel" not in groups:
            groups.append("wheel")
        return groups


class UserConfig(BaseModel):
    users: list[User] = Field(default_factory=list)
    #: Disabling root entirely is the safer default once a sudo user exists.
    root_login_enabled: bool = False

    @property
    def has_sudo_user(self) -> bool:
        return any(user.sudo for user in self.users)


class Credentials(BaseModel):
    """Contents of the separate credentials file. Never serialised into the
    main configuration."""

    #: Plaintext passwords by username, consumed immediately by ``chpasswd``
    #: and never written to the target system.
    user_passwords: dict[str, str] = Field(default_factory=dict)
    root_password: str | None = None
    #: LUKS passphrase. Prompted for interactively when absent.
    encryption_passphrase: str | None = None
