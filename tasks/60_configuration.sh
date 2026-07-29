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

        # genfstab lists the active swapfile, but without a priority, which would
        # let the kernel stripe everyday paging across zram and disk. Its line is
        # dropped and replaced with one that pins the priority below zram.
        fstab_content="$(printf '%s\n' "${fstab_content}" | grep -v '[[:space:]]swap[[:space:]]')"

        write_target_file /etc/fstab "${fstab_content}
$(swapfile_fstab_entry)" || return 1
    fi
    configure_installed_system || return 1
    mkinitcpio_hooks="$(build_mkinitcpio_hooks)"
    write_target_file /etc/mkinitcpio.conf "${mkinitcpio_hooks}
" || return 1
    configure_zram || return 1
    configure_snapper || return 1
    configure_graphical_session
}
task_configuration_verify() {
    verify_target_file /etc/fstab &&
        verify_target_file /etc/hostname &&
        verify_zram_configuration &&
        verify_graphical_session
}
# Hibernation cannot be verified here: resume_offset lands in limine.conf, which
# the bootloader task writes afterwards. It is checked in the readiness task.
task_configuration_cleanup() { return 0; }
task_configuration_rollback() { return 0; }
