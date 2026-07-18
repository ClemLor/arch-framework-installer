#!/usr/bin/env bash

if [[ -n "${ARCH_INSTALLER_LUKS_LOADED:-}" ]]; then return 0; fi
readonly ARCH_INSTALLER_LUKS_LOADED="true"

luks_device() { get_system_partition_path; }
luks_mapping_path() { printf '/dev/mapper/%s' "${LUKS_NAME}"; }

root_block_device() {
    if [[ "${LUKS_ENABLED}" == "true" ]]; then
        luks_mapping_path
    else
        get_system_partition_path
    fi
}

validate_luks_dependencies() {
    require_commands_for_mode "LUKS2" cryptsetup
}

format_and_open_luks() {
    local device
    if [[ "${LUKS_ENABLED}" != "true" ]]; then
        info "Disk encryption is disabled; Btrfs will use $(get_system_partition_path) directly."
        return 0
    fi
    device="$(luks_device)"
    run_command cryptsetup luksFormat --type luks2 "${device}" || return 1
    run_command cryptsetup open "${device}" "${LUKS_NAME}"
}

verify_luks() {
    [[ "${DRY_RUN:-false}" == "true" ]] && return 0
    if [[ "${LUKS_ENABLED}" != "true" ]]; then
        [[ -b "$(get_system_partition_path)" ]]
        return
    fi
    cryptsetup isLuks "$(luks_device)" && [[ -b "$(luks_mapping_path)" ]]
}

close_luks_mapping() {
    [[ "${LUKS_ENABLED}" == "true" ]] || return 0
    [[ "${DRY_RUN:-false}" == "true" ]] && return 0
    [[ -e "$(luks_mapping_path)" ]] || return 0
    run_command cryptsetup close "${LUKS_NAME}"
}

luks_has_tpm2_token() {
    local metadata

    metadata="$(capture_logged_command cryptsetup luksDump --dump-json-metadata "$(luks_device)")" || return 1
    capture_logged_command jq --exit-status \
        'any(.tokens[]?; .type == "systemd-tpm2")' <<<"${metadata}" >/dev/null
}

enroll_luks_tpm2() {
    [[ "${LUKS_ENABLED}" == "true" && "${TPM2_ENABLED}" == "true" ]] || return 0
    if [[ "${DRY_RUN:-false}" != "true" ]] && luks_has_tpm2_token; then
        info "A systemd TPM2 token is already enrolled on $(luks_device)."
        return 0
    fi
    run_command systemd-cryptenroll --tpm2-device=auto --tpm2-pcrs=7 "$(luks_device)"
}
