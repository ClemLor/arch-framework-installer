#!/usr/bin/env bash

if [[ -n "${ARCH_INSTALLER_SERVICES_LOADED:-}" ]]; then return 0; fi
readonly ARCH_INSTALLER_SERVICES_LOADED="true"

configure_services() {
    local root
    local service
    root="$(project_root)"
    while IFS= read -r service; do
        [[ -n "${service}" ]] || continue
        run_in_chroot systemctl enable "${service}" || return 1
    done < <(sed -e 's/[[:space:]]*#.*$//' -e '/^[[:space:]]*$/d' "${root}/services/enable.list")
    while IFS= read -r service; do
        [[ -n "${service}" ]] || continue
        run_in_chroot systemctl disable "${service}" || return 1
    done < <(sed -e 's/[[:space:]]*#.*$//' -e '/^[[:space:]]*$/d' "${root}/services/disable.list")
}
