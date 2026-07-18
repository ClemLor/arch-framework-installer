#!/usr/bin/env bash

task_configuration_name() { printf 'System configuration'; }
task_configuration_validate() { require_commands_for_mode "System configuration" arch-chroot genfstab; }
task_configuration_execute() {
    local fstab_content
    local mkinitcpio_hooks
    if [[ "${DRY_RUN}" == "true" ]]; then
        run_command genfstab -U "${MOUNT_ROOT}"
    else
        fstab_content="$(genfstab -U "${MOUNT_ROOT}")" || return 1
        write_target_file /etc/fstab "${fstab_content}
" || return 1
    fi
    configure_installed_system || return 1
    if [[ "${LUKS_ENABLED}" == "true" ]]; then
        mkinitcpio_hooks='HOOKS=(base systemd autodetect microcode modconf kms keyboard sd-vconsole block sd-encrypt filesystems fsck)'
    else
        mkinitcpio_hooks='HOOKS=(base systemd autodetect microcode modconf kms keyboard sd-vconsole block filesystems fsck)'
    fi
    write_target_file /etc/mkinitcpio.conf "${mkinitcpio_hooks}
" || return 1
    write_target_file /etc/systemd/zram-generator.conf '[zram0]
zram-size = ram / 2
compression-algorithm = zstd
' || return 1
    configure_snapper
}
task_configuration_verify() { verify_target_file /etc/fstab && verify_target_file /etc/hostname; }
task_configuration_cleanup() { return 0; }
task_configuration_rollback() { return 0; }
