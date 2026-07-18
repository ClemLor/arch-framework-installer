#!/usr/bin/env bash

if [[ -n "${ARCH_INSTALLER_USERS_LOADED:-}" ]]; then return 0; fi
readonly ARCH_INSTALLER_USERS_LOADED="true"

create_installed_user() {
    run_in_chroot useradd --create-home --groups "${USER_GROUPS}" --shell "${USER_SHELL}" "${USERNAME}" || return 1
    if [[ "${DRY_RUN:-false}" == "true" ]]; then
        run_command arch-chroot "${MOUNT_ROOT}" passwd "${USERNAME}"
    else
        info "Set the password for ${USERNAME}."
        arch-chroot "${MOUNT_ROOT}" passwd "${USERNAME}" || return 1
    fi
    write_target_file /etc/sudoers.d/10-wheel '%wheel ALL=(ALL:ALL) ALL
' || return 1
    [[ "${DRY_RUN:-false}" == "true" ]] || chmod 0440 "${MOUNT_ROOT}/etc/sudoers.d/10-wheel"
}
