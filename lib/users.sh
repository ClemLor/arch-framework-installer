#!/usr/bin/env bash

if [[ -n "${ARCH_INSTALLER_USERS_LOADED:-}" ]]; then return 0; fi
readonly ARCH_INSTALLER_USERS_LOADED="true"

create_installed_user() {
    if [[ "${DRY_RUN:-false}" == "true" ]]; then
        run_in_chroot useradd --create-home --groups "${USER_GROUPS}" --shell "${USER_SHELL}" "${USERNAME}" || return 1
        run_command arch-chroot "${MOUNT_ROOT}" passwd "${USERNAME}" || return 1
    elif run_in_chroot id "${USERNAME}" >/dev/null 2>&1; then
        info "Updating existing account ${USERNAME}."
        run_in_chroot usermod --groups "${USER_GROUPS}" --shell "${USER_SHELL}" "${USERNAME}" || return 1
    else
        run_in_chroot useradd --create-home --groups "${USER_GROUPS}" --shell "${USER_SHELL}" "${USERNAME}" || return 1
        info "Set the password for ${USERNAME}."
        log_message "COMMAND" "interactive: arch-chroot ${MOUNT_ROOT} passwd ${USERNAME}"
        arch-chroot "${MOUNT_ROOT}" passwd "${USERNAME}" || return 1
    fi
    write_target_file /etc/sudoers.d/10-wheel '%wheel ALL=(ALL:ALL) ALL
' || return 1
    run_command chmod 0440 "${MOUNT_ROOT}/etc/sudoers.d/10-wheel" || return 1
    [[ "${DRY_RUN:-false}" == "true" ]] || run_in_chroot visudo -cf /etc/sudoers.d/10-wheel
}
