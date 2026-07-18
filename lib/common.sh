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
    local efi_root="${EFI_SYSFS_ROOT:-/sys/firmware/efi}"
    local platform_size

    [[ -d "${efi_root}" ]] || return 1

    if [[ -r "${efi_root}/fw_platform_size" ]]; then
        platform_size="$(<"${efi_root}/fw_platform_size")"
        [[ "${platform_size}" == "32" || "${platform_size}" == "64" ]] || return 1
    fi

    return 0
}

get_uefi_platform_size() {
    local efi_root="${EFI_SYSFS_ROOT:-/sys/firmware/efi}"

    if [[ -r "${efi_root}/fw_platform_size" ]]; then
        trim "$(<"${efi_root}/fw_platform_size")"
    else
        printf '%s' "unknown"
    fi
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

require_real_installation_enabled() {
    if [[ "${DRY_RUN:-false}" == "true" ]]; then
        return 0
    fi

    if [[ "${ENABLE_REAL_INSTALLATION:-false}" != "true" ]]; then
        error "Real installation is disabled. Set ENABLE_REAL_INSTALLATION=true after reviewing a dry-run."
        return 1
    fi
}

require_commands_for_mode() {
    local context="$1"
    shift
    local command
    local -a missing=()

    for command in "$@"; do
        command_exists "${command}" || missing+=("${command}")
    done

    (( ${#missing[@]} == 0 )) && return 0

    if [[ "${DRY_RUN:-false}" == "true" ]]; then
        warn "${context}: commands unavailable but not executed in dry-run: ${missing[*]}"
        return 0
    fi

    error "${context}: missing required commands: ${missing[*]}"
    return 1
}
