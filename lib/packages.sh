#!/usr/bin/env bash

if [[ -n "${ARCH_INSTALLER_PACKAGES_LOADED:-}" ]]; then return 0; fi
readonly ARCH_INSTALLER_PACKAGES_LOADED="true"

verify_required_packages() {
    local package
    for package in base linux limine niri dms-shell-niri fish fwupd fprintd greetd snapper; do
        run_in_chroot pacman -Q "${package}" >/dev/null || return 1
    done
}
