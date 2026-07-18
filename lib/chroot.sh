#!/usr/bin/env bash

if [[ -n "${ARCH_INSTALLER_CHROOT_LOADED:-}" ]]; then return 0; fi
readonly ARCH_INSTALLER_CHROOT_LOADED="true"

run_in_chroot() {
    run_command arch-chroot "${MOUNT_ROOT}" "$@"
}

write_target_file() {
    local path="$1"
    local content="$2"
    if [[ "${DRY_RUN:-false}" == "true" ]]; then
        log_message "DRY-RUN" "write ${MOUNT_ROOT}${path}"
        printf '[DRY-RUN] write %s\n' "${MOUNT_ROOT}${path}"
        return 0
    fi
    log_message "WRITE" "${MOUNT_ROOT}${path}"
    mkdir -p "$(dirname "${MOUNT_ROOT}${path}")" || return 1
    printf '%s' "${content}" >"${MOUNT_ROOT}${path}"
}
