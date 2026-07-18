#!/usr/bin/env bash

if [[ -n "${ARCH_INSTALLER_LUKS_LOADED:-}" ]]; then return 0; fi
readonly ARCH_INSTALLER_LUKS_LOADED="true"

luks_device() { get_system_partition_path; }
luks_mapping_path() { printf '/dev/mapper/%s' "${LUKS_NAME}"; }

validate_luks_dependencies() {
    require_commands_for_mode "LUKS2" cryptsetup
}

format_and_open_luks() {
    local device
    device="$(luks_device)"
    run_command cryptsetup luksFormat --type luks2 "${device}" || return 1
    run_command cryptsetup open "${device}" "${LUKS_NAME}"
}

verify_luks() {
    [[ "${DRY_RUN:-false}" == "true" ]] && return 0
    cryptsetup isLuks "$(luks_device)" && [[ -b "$(luks_mapping_path)" ]]
}

close_luks_mapping() {
    [[ "${DRY_RUN:-false}" == "true" ]] && return 0
    [[ -e "$(luks_mapping_path)" ]] || return 0
    run_command cryptsetup close "${LUKS_NAME}"
}

enroll_luks_tpm2() {
    [[ "${TPM2_ENABLED}" == "true" ]] || return 0
    run_command systemd-cryptenroll --tpm2-device=auto "$(luks_device)"
}
