#!/usr/bin/env bash

if [[ -n "${ARCH_INSTALLER_PACSTRAP_LOADED:-}" ]]; then return 0; fi
readonly ARCH_INSTALLER_PACSTRAP_LOADED="true"

read_package_list() {
    sed -e 's/[[:space:]]*#.*$//' -e '/^[[:space:]]*$/d' "$1"
}

collect_packages() {
    local root
    local list
    root="$(project_root)"
    for list in base firmware framework desktop development fonts multimedia optional; do
        [[ -s "${root}/packages/${list}.list" ]] || continue
        read_package_list "${root}/packages/${list}.list"
    done | LC_ALL=C sort -u
}

install_base_system() {
    local -a packages=()
    mapfile -t packages < <(collect_packages)
    (( ${#packages[@]} > 0 )) || { error "No packages configured."; return 1; }
    run_command pacstrap -K "${MOUNT_ROOT}" "${packages[@]}"
}
