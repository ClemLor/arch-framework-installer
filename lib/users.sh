#!/usr/bin/env bash

if [[ -n "${ARCH_INSTALLER_USERS_LOADED:-}" ]]; then return 0; fi
readonly ARCH_INSTALLER_USERS_LOADED="true"

prepare_installed_user_home() {
    local home_path="/home/${USERNAME}"

    run_in_chroot test -d "${home_path}" || return 1
    run_in_chroot chown "${USERNAME}:${USERNAME}" "${home_path}" || return 1
    run_in_chroot install -d -m0700 -o "${USERNAME}" -g "${USERNAME}" \
        "${home_path}/.cache" \
        "${home_path}/.config" \
        "${home_path}/.local" \
        "${home_path}/.local/share" || return 1
    run_in_chroot install -d -m0755 -o "${USERNAME}" -g "${USERNAME}" \
        "${home_path}/.config/systemd" \
        "${home_path}/.config/systemd/user" \
        "${home_path}/.local/bin"
}

verify_installed_user_home() {
    local home_path="/home/${USERNAME}"
    local path

    [[ "${DRY_RUN:-false}" == "true" ]] && return 0
    for path in \
        "${home_path}" \
        "${home_path}/.cache" \
        "${home_path}/.config" \
        "${home_path}/.config/systemd/user" \
        "${home_path}/.local" \
        "${home_path}/.local/bin" \
        "${home_path}/.local/share"; do
        run_in_chroot runuser --user "${USERNAME}" -- test -w "${path}" || {
            error "The installed user cannot write to ${path}."
            return 1
        }
    done
}

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
    prepare_installed_user_home || return 1
    write_target_file /etc/sudoers.d/10-wheel '%wheel ALL=(ALL:ALL) ALL
' || return 1
    run_command chmod 0440 "${MOUNT_ROOT}/etc/sudoers.d/10-wheel" || return 1
    [[ "${DRY_RUN:-false}" == "true" ]] || run_in_chroot visudo -cf /etc/sudoers.d/10-wheel
}
