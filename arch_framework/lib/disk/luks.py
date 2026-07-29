"""LUKS2 and TPM2 enrolment.

The ordering is the safety property, not the commands:

1. format with the passphrase the user supplied;
2. open the container so the rest of the install can proceed;
3. add a recovery key as a second keyslot, show it, and require the user to
   confirm they have recorded it;
4. only then enrol the TPM2.

The recovery key comes before enrolment because a TPM2 seal is bound to firmware
and Secure Boot state, and a firmware update can stop it opening. Enrolling
first would leave a window in which the machine could become unopenable. The
original passphrase is never removed — it stays as the third way in.

Passphrases are passed on stdin, never as arguments: an argument is visible in
the process list to every user on the machine.
"""

from __future__ import annotations

import secrets
from pathlib import Path

from .. import log
from ..command import CommandRunner, get_runner
from ..exceptions import InstallerError
from ..models import DiskConfig, EncryptionConfig

#: Stated rather than left to defaults, so the installed system does not change
#: behaviour when a future cryptsetup changes its mind.
LUKS_FORMAT_OPTIONS = [
    "--type", "luks2",
    "--pbkdf", "argon2id",
    "--cipher", "aes-xts-plain64",
    "--key-size", "512",
    "--hash", "sha512",
]

#: Groups of five, which is how a key actually gets transcribed onto paper.
RECOVERY_KEY_GROUPS = 8
RECOVERY_KEY_GROUP_SIZE = 5

#: Excludes characters that are misread in handwriting: I, O, 0, 1.
RECOVERY_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"

#: /run is tmpfs on the live ISO, so the key never reaches a disk. The name is
#: fixed rather than including a pid: it appears in the command journal, and a
#: journal that differs between runs cannot be compared against a golden file.
RECOVERY_KEYFILE = Path("/run/arch-framework-installer-recovery.key")

DRY_RUN_RECOVERY_KEY = "XXXXX-XXXXX-XXXXX-XXXXX-XXXXX-XXXXX-XXXXX-XXXXX"


def generate_recovery_key() -> str:
    groups = [
        "".join(
            secrets.choice(RECOVERY_ALPHABET) for _ in range(RECOVERY_KEY_GROUP_SIZE)
        )
        for _ in range(RECOVERY_KEY_GROUPS)
    ]
    return "-".join(groups)


def format_container(
    disk: DiskConfig,
    passphrase: str,
    *,
    runner: CommandRunner | None = None,
) -> None:
    runner = runner or get_runner()

    if not passphrase:
        raise InstallerError("a LUKS passphrase is required")

    log.info(f"Creating the LUKS2 container on {disk.system_partition}")
    runner.run(
        [
            "cryptsetup",
            "luksFormat",
            *LUKS_FORMAT_OPTIONS,
            "--batch-mode",
            "--key-file",
            "-",
            disk.system_partition,
        ],
        input_text=passphrase,
    )
    log.success("LUKS2 container created.")


def open_container(
    disk: DiskConfig,
    encryption: EncryptionConfig,
    passphrase: str,
    *,
    runner: CommandRunner | None = None,
) -> None:
    runner = runner or get_runner()
    log.info(f"Opening the container as {encryption.mapper_name}")
    runner.run(
        [
            "cryptsetup",
            "open",
            "--key-file",
            "-",
            disk.system_partition,
            encryption.mapper_name,
        ],
        input_text=passphrase,
    )


def add_recovery_key(
    disk: DiskConfig,
    passphrase: str,
    recovery_key: str,
    *,
    runner: CommandRunner | None = None,
) -> None:
    """Add the recovery key as a second keyslot.

    ``luksAddKey`` needs the existing key on stdin and the new one as a file, so
    the new key is written to tmpfs with owner-only permissions and removed
    immediately. It never touches a disk.
    """
    runner = runner or get_runner()

    keyfile = RECOVERY_KEYFILE

    if runner.dry_run:
        log.info(f"[DRY-RUN] write the recovery key to {keyfile} (mode 0600)")
        runner.run(
            [
                "cryptsetup",
                "luksAddKey",
                "--batch-mode",
                "--key-file",
                "-",
                disk.system_partition,
                str(keyfile),
            ],
            input_text=passphrase,
        )
        return

    try:
        keyfile.touch(mode=0o600, exist_ok=False)
        keyfile.write_text(recovery_key, encoding="utf-8")

        runner.run(
            [
                "cryptsetup",
                "luksAddKey",
                "--batch-mode",
                "--key-file",
                "-",
                disk.system_partition,
                str(keyfile),
            ],
            input_text=passphrase,
        )
    finally:
        keyfile.unlink(missing_ok=True)

    log.success("Recovery key added as a second keyslot.")


def show_recovery_key(recovery_key: str, *, interactive: bool = True) -> None:
    """Display the key and require acknowledgement.

    Blocking is intentional: a key printed into a scrolling log is a key nobody
    wrote down.
    """
    log.section("Recovery key")
    log.warn("Write this down now. It is the way in if the TPM2 stops working.")
    print(f"\n    {recovery_key}\n")

    if not interactive:
        log.warn("Non-interactive run: acknowledgement skipped.")
        return

    while True:
        answer = input("Type CONFIRMED once you have recorded it: ").strip()
        if answer == "CONFIRMED":
            return
        log.warn("Not confirmed. The installation will not continue until it is.")


def enroll_tpm2(
    disk: DiskConfig,
    encryption: EncryptionConfig,
    passphrase: str,
    *,
    runner: CommandRunner | None = None,
) -> None:
    """Seal a key to the TPM2 so the disk opens without a typed passphrase.

    PCR 0 covers the firmware and PCR 7 the Secure Boot state. More PCRs is
    stricter and breaks more often on updates; fewer means a tampered boot chain
    could still unseal.
    """
    runner = runner or get_runner()
    log.info(f"Enrolling the TPM2 against PCRs {encryption.tpm2_pcrs}")
    runner.run(
        [
            "systemd-cryptenroll",
            "--unlock-key-file=/dev/stdin",
            "--tpm2-device=auto",
            f"--tpm2-pcrs={encryption.tpm2_pcrs}",
            disk.system_partition,
        ],
        input_text=passphrase,
    )
    log.success("TPM2 enrolled.")


def partition_uuid(
    partition: str, *, runner: CommandRunner | None = None
) -> str:
    """UUID of a partition, or a marked placeholder during a dry run."""
    runner = runner or get_runner()
    return runner.derived(
        ["blkid", "--match-tag", "UUID", "--output", "value", partition],
        placeholder=f"<UUID-of-{partition}>",
    )


def close_container(
    encryption: EncryptionConfig, *, runner: CommandRunner | None = None
) -> None:
    runner = runner or get_runner()
    runner.run(["cryptsetup", "close", encryption.mapper_name], check=False)
