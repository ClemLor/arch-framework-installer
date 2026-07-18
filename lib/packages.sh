#!/usr/bin/env bash

if [[ -n "${ARCH_INSTALLER_PACKAGES_LOADED:-}" ]]; then return 0; fi
readonly ARCH_INSTALLER_PACKAGES_LOADED="true"

verify_required_packages() {
    local package

    while IFS= read -r package; do
        [[ -n "${package}" ]] || continue
        run_in_chroot pacman -Q "${package}" >/dev/null || return 1
    done < <(collect_packages)
}
