"""Stage orchestration.

The stage list is the installation. Each one is named, recorded when it
completes, and skipped on a resume, so a failure at the bootloader does not mean
repartitioning.

Two things are deliberate about the ordering:

* the safety re-check happens inside the partition stage, immediately before the
  first destructive command, not here and not in the menu;
* the recovery key is added and acknowledged before the TPM2 is enrolled, so
  there is never a moment where the only way in is a seal that a firmware update
  could invalidate.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from . import log
from .bootloader import limine
from .command import CommandRunner, get_runner
from .configure import apply as apply_configuration
from .disk import filesystem, luks, partitioning
from .disk.source import FixtureSource, get_source
from .exceptions import EnvironmentError_, InstallerError, StageError
from .hardware import Hardware
from .models import Credentials, InstallConfig
from .models.device import SWAP_SUBVOLUME
from .packages import pacstrap
from .state import InstallState
from .target import TargetSystem
from .users import create_users


@dataclass
class Stage:
    key: str
    description: str
    run: Callable[["Installer"], None]


class Installer:
    def __init__(
        self,
        config: InstallConfig,
        credentials: Credentials,
        *,
        runner: CommandRunner | None = None,
        state: InstallState | None = None,
        interactive: bool = True,
    ) -> None:
        self.config = config
        self.credentials = credentials
        self.runner = runner or get_runner()
        self.state = state or InstallState.load_or_new(config)
        self.interactive = interactive
        self.target = TargetSystem(runner=self.runner)

        # Filled in as the stages progress.
        self.recovery_key: str | None = None
        self.luks_uuid: str = ""
        self.resume_offset: str | None = None

    # -- derived ------------------------------------------------------------

    @property
    def mapper_path(self) -> str:
        if self.config.encryption.enabled:
            return self.config.encryption.mapper_path
        return self.config.disk.system_partition

    @property
    def passphrase(self) -> str:
        phrase = self.credentials.encryption_passphrase
        if not phrase:
            raise StageError(
                "no encryption passphrase available; supply one in the "
                "credentials file or run interactively"
            )
        return phrase

    # -- preflight ----------------------------------------------------------

    def preflight(self) -> None:
        """Refuse an environment that cannot produce a working system."""
        hardware = Hardware()
        host = hardware.info()

        if not self.runner.dry_run:
            # Recorded devices mean this is not the machine being described.
            # Partitioning a real disk from facts read out of a file is never
            # right, and the fixture path exists precisely so development
            # happens off-machine.
            if isinstance(get_source(), FixtureSource):
                raise EnvironmentError_(
                    "refusing to install while reading devices from a fixture; "
                    "recorded devices describe another machine"
                )
            if not host.live_environment:
                raise EnvironmentError_(
                    "installation must run from the Arch live ISO"
                )
            if not host.uefi:
                raise EnvironmentError_("installation requires UEFI boot mode")

        if host.memory is not None:
            self.config.validate_hibernation(host.memory.bytes)

        if self.config.encryption.enabled and not self.credentials.encryption_passphrase:
            raise StageError("encryption is enabled but no passphrase was supplied")

        log.success("Preflight checks passed.")

    # -- stages -------------------------------------------------------------

    def stage_partition(self) -> None:
        partitioning.partition(self.config.disk, runner=self.runner)
        partitioning.format_efi(self.config.disk, runner=self.runner)

    def stage_encrypt(self) -> None:
        if not self.config.encryption.enabled:
            log.info("Encryption disabled; nothing to do.")
            return

        luks.format_container(self.config.disk, self.passphrase, runner=self.runner)
        luks.open_container(
            self.config.disk, self.config.encryption, self.passphrase, runner=self.runner
        )

    def stage_recovery_key(self) -> None:
        """Before TPM2 enrolment, never after."""
        if not self.config.encryption.enabled:
            return

        key = (
            luks.DRY_RUN_RECOVERY_KEY
            if self.runner.dry_run
            else luks.generate_recovery_key()
        )
        self.recovery_key = key

        luks.add_recovery_key(
            self.config.disk, self.passphrase, key, runner=self.runner
        )
        luks.show_recovery_key(
            key, interactive=self.interactive and not self.runner.dry_run
        )

    def stage_filesystem(self) -> None:
        filesystem.create_filesystem(
            self.config.disk, self.mapper_path, runner=self.runner
        )
        filesystem.create_subvolumes(
            self.config.disk, self.mapper_path, runner=self.runner
        )

    def stage_mount(self) -> None:
        filesystem.mount_all(self.config.disk, self.mapper_path, runner=self.runner)

        if SWAP_SUBVOLUME in self.config.disk.subvolumes:
            filesystem.create_swapfile(self.config.swap, runner=self.runner)
            if self.config.swap.hibernation_enabled:
                self.resume_offset = filesystem.resume_offset(runner=self.runner)

    def stage_base_system(self) -> None:
        pacstrap(self.config, self.target.root, runner=self.runner)

    def stage_configure(self) -> None:
        apply_configuration(
            self.config, self.target, self.mapper_path, runner=self.runner
        )

    def stage_users(self) -> None:
        create_users(self.config.users, self.credentials, self.target)

    def stage_bootloader(self) -> None:
        self.luks_uuid = luks.partition_uuid(
            self.config.disk.system_partition, runner=self.runner
        )
        limine.install(
            self.config,
            self.target,
            luks_uuid=self.luks_uuid,
            mapper_path=self.mapper_path,
            resume_offset=self.resume_offset,
            runner=self.runner,
        )

    def stage_tpm2(self) -> None:
        """Last, because a broken seal must not be able to strand a system that
        is otherwise not yet finished."""
        if not (self.config.encryption.enabled and self.config.encryption.tpm2_enabled):
            return

        if self.recovery_key is None and not self.state.is_done("recovery_key"):
            raise StageError(
                "refusing to enrol the TPM2 before a recovery key exists"
            )

        luks.enroll_tpm2(
            self.config.disk, self.config.encryption, self.passphrase, runner=self.runner
        )

    def stage_cleanup(self) -> None:
        filesystem.unmount_all(runner=self.runner)

    # -- driver -------------------------------------------------------------

    def stages(self) -> list[Stage]:
        return [
            Stage("partition", "Partitioning the disk", Installer.stage_partition),
            Stage("encrypt", "Creating the encrypted container", Installer.stage_encrypt),
            Stage("recovery_key", "Adding a recovery key", Installer.stage_recovery_key),
            Stage("filesystem", "Creating the filesystem", Installer.stage_filesystem),
            Stage("mount", "Mounting the target", Installer.stage_mount),
            Stage("base_system", "Installing packages", Installer.stage_base_system),
            Stage("configure", "Configuring the system", Installer.stage_configure),
            Stage("users", "Creating user accounts", Installer.stage_users),
            Stage("bootloader", "Installing the bootloader", Installer.stage_bootloader),
            Stage("tpm2", "Enrolling the TPM2", Installer.stage_tpm2),
            Stage("cleanup", "Unmounting", Installer.stage_cleanup),
        ]

    def run(self) -> int:
        self.preflight()

        for stage in self.stages():
            if self.state.is_done(stage.key):
                log.info(f"Skipping {stage.key}: already completed.")
                continue

            log.section(stage.description)
            try:
                stage.run(self)
            except InstallerError as exc:
                log.error(f"Stage {stage.key} failed: {exc}")
                log.info(
                    "Fix the cause and run again; completed stages are skipped."
                )
                return 1

            if not self.runner.dry_run:
                self.state.mark_done(stage.key)

        if self.runner.dry_run:
            log.success("Dry run complete. Nothing was changed.")
            return 0

        self.state.clear()
        log.section("Done")
        log.success("Installation complete.")
        if self.recovery_key:
            log.warn("Keep the recovery key. It is not recoverable from the system.")
        for package in self.config.bootloader.aur_packages:
            log.info(f"After first boot, install {package} from the AUR.")
        return 0


def install(
    config: InstallConfig,
    credentials: Credentials,
    *,
    state_path: Path | None = None,
    interactive: bool = True,
) -> int:
    state = InstallState.load_or_new(config, state_path)
    return Installer(
        config, credentials, state=state, interactive=interactive
    ).run()
