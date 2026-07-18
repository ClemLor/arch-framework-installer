#!/usr/bin/env bash

# ==============================================================================
# Module: common
#
# Purpose:
#   Provide general-purpose helper functions shared by the installer modules.
#
# Idempotent:
#   Yes
# ==============================================================================

if [[ -n "${ARCH_INSTALLER_COMMON_LOADED:-}" ]]; then
    return 0
fi

readonly ARCH_INSTALLER_COMMON_LOADED="true"

project_root() {
    local source_path

    source_path="${BASH_SOURCE[0]}"

    while [[ -L "${source_path}" ]]; do
        source_path="$(readlink "${source_path}")"
    done

    cd "$(dirname "${source_path}")/.." >/dev/null 2>&1
    pwd
}

command_exists() {
    command -v "$1" >/dev/null 2>&1
}

is_root() {
    [[ "${EUID}" -eq 0 ]]
}

require_root() {
    if ! is_root; then
        fatal "This command must be run as root."
    fi
}

is_uefi_system() {
    [[ -d /sys/firmware/efi/efivars ]]
}

is_architecture_supported() {
    [[ "$(uname -m)" == "x86_64" ]]
}

trim() {
    local value="$*"

    value="${value#"${value%%[![:space:]]*}"}"
    value="${value%"${value##*[![:space:]]}"}"

    printf '%s' "${value}"
}
