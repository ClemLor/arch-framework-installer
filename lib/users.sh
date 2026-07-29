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

# Whether root has a usable password.
#
# `passwd --status` reports P for a usable password, L for locked and NP for none.
# A fresh pacstrap leaves root locked, so this distinguishes "already set" from
# "never set" and keeps the prompt out of a re-run.
root_password_is_set() {
    local status

    status="$(run_in_chroot passwd --status root)" || return 1
    [[ "$(awk '{ print $2 }' <<<"${status}")" == "P" ]]
}

# The fallback when sudo is unavailable.
#
# Asked interactively, exactly like the user's password, and never stored in the
# configuration. It exists so that a mistake in group membership, a broken
# sudoers file or a damaged user account is recoverable from a TTY instead of
# requiring a reinstall.
set_root_password() {
    if [[ "${DRY_RUN:-false}" == "true" ]]; then
        run_command arch-chroot "${MOUNT_ROOT}" passwd root
        return 0
    fi

    if root_password_is_set; then
        info "root already has a password; leaving it unchanged."
        return 0
    fi

    info "Set the root password. This is the way back in if sudo ever fails."
    log_message "COMMAND" "interactive: arch-chroot ${MOUNT_ROOT} passwd root"
    arch-chroot "${MOUNT_ROOT}" passwd root
}

# A locked root account plus any fault in the sudo path leaves no way in at all,
# which on an encrypted disk means reinstalling.
verify_root_password() {
    [[ "${DRY_RUN:-false}" == "true" ]] && return 0

    if ! root_password_is_set; then
        error "root has no usable password; there would be no fallback if sudo failed."
        return 1
    fi
}

# Membership is checked separately from the sudoers file.
#
# The file granting %wheel and the account being in wheel are two independent
# facts, and each looks correct on its own. Only together do they give the user
# any administrative access, so verifying one has never implied the other.
verify_installed_user_privileges() {
    local groups

    [[ "${DRY_RUN:-false}" == "true" ]] && return 0

    groups="$(run_in_chroot id --name --groups "${USERNAME}")" || {
        error "Could not read the groups of ${USERNAME}."
        return 1
    }

    if [[ " ${groups} " != *" wheel "* ]]; then
        error "${USERNAME} is not in the wheel group; sudo would not work."
        error "Groups: ${groups}"
        return 1
    fi

    # An empty sudo binary check is not enough: the drop-in is useless if the
    # package is absent, and pacstrap could have been given a shortened list.
    run_in_chroot command -v sudo >/dev/null || {
        error "sudo is not installed in the target."
        return 1
    }

    # Asks sudo itself whether the rule applies, rather than trusting that a
    # syntactically valid file grants what it appears to grant.
    run_in_chroot sudo --list --user "${USERNAME}" >/dev/null || {
        error "sudo does not grant ${USERNAME} any privileges."
        return 1
    }
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
    set_root_password || return 1
    write_target_file /etc/sudoers.d/10-wheel '%wheel ALL=(ALL:ALL) ALL
' || return 1
    run_command chmod 0440 "${MOUNT_ROOT}/etc/sudoers.d/10-wheel" || return 1
    [[ "${DRY_RUN:-false}" == "true" ]] || run_in_chroot visudo -cf /etc/sudoers.d/10-wheel
}
