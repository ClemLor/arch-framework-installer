"""LUKS2 and TPM2 settings.

TPM2 auto-unlock is the piece archinstall does not provide, and the reason this
project owns its installer rather than wrapping one. Enrolling a TPM2 key
without also having a recovery key is a way to lose a machine to a firmware
update, so that pairing is enforced here rather than left to documentation.
"""

from __future__ import annotations

from pydantic import BaseModel, model_validator


class EncryptionConfig(BaseModel):
    enabled: bool = True
    mapper_name: str = "cryptroot"
    tpm2_enabled: bool = True
    #: PCRs sealed against. 0 covers firmware, 7 the Secure Boot state. Adding
    #: more makes the seal stricter and firmware updates more likely to break
    #: unlocking.
    tpm2_pcrs: str = "0+7"
    #: A recovery key is generated and shown to the user before enrolling the
    #: TPM2, and is the only way back in when the PCR seal stops matching.
    recovery_key: bool = True

    @model_validator(mode="after")
    def _tpm2_requires_luks(self) -> "EncryptionConfig":
        if self.tpm2_enabled and not self.enabled:
            raise ValueError("tpm2_enabled requires encryption to be enabled")
        if self.tpm2_enabled and not self.recovery_key:
            raise ValueError(
                "TPM2 enrolment without a recovery key can lock you out of the "
                "machine after a firmware update; recovery_key cannot be disabled "
                "while tpm2_enabled is set"
            )
        return self

    @property
    def mapper_path(self) -> str:
        return f"/dev/mapper/{self.mapper_name}"

    @property
    def packages(self) -> tuple[str, ...]:
        if not self.enabled:
            return ()
        if self.tpm2_enabled:
            return ("cryptsetup", "tpm2-tss", "tpm2-tools")
        return ("cryptsetup",)
