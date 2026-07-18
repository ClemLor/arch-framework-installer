#!/usr/bin/env bash

if [[ -n "${ARCH_INSTALLER_VERIFY_LOADED:-}" ]]; then return 0; fi
readonly ARCH_INSTALLER_VERIFY_LOADED="true"

verify_target_file() {
    [[ "${DRY_RUN:-false}" == "true" ]] || [[ -s "${MOUNT_ROOT}$1" ]]
}
