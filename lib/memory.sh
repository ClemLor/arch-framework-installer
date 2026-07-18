#!/usr/bin/env bash

if [[ -n "${ARCH_INSTALLER_MEMORY_LOADED:-}" ]]; then return 0; fi
readonly ARCH_INSTALLER_MEMORY_LOADED="true"

configure_zram() {
    local config_path='/etc/systemd/zram-generator.conf'

    if [[ "${ZRAM_ENABLED}" == "true" ]]; then
        write_target_file "${config_path}" '[zram0]
zram-size = ram / 2
compression-algorithm = zstd
'
        return
    fi

    info "Zram is disabled; removing the installer-managed target configuration."
    run_command rm -f "${MOUNT_ROOT}${config_path}"
}

verify_zram_configuration() {
    local config_path="${MOUNT_ROOT}/etc/systemd/zram-generator.conf"

    if [[ "${DRY_RUN:-false}" == "true" ]]; then
        return 0
    fi

    if [[ "${ZRAM_ENABLED}" == "true" ]]; then
        [[ -s "${config_path}" ]] || return 1
        grep -Fq 'compression-algorithm = zstd' "${config_path}"
        return
    fi

    [[ ! -e "${config_path}" ]]
}
