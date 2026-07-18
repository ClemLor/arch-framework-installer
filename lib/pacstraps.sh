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

refresh_package_databases() {
    run_command pacman --sync --refresh --noconfirm
}

validate_configured_packages_available() {
    local package
    local -a packages=()
    local -a missing=()

    mapfile -t packages < <(collect_packages)
    for package in "${packages[@]}"; do
        if ! run_command pacman --sync --info -- "${package}" >/dev/null 2>&1; then
            missing+=("${package}")
        fi
    done

    if (( ${#missing[@]} > 0 )); then
        error "Packages unavailable from configured pacman repositories: ${missing[*]}"
        error "AUR and proprietary packages must not be passed to pacstrap."
        return 1
    fi

    success "All configured pacstrap packages are available."
}

prepare_package_sources() {
    if [[ "${DRY_RUN:-false}" == "true" ]]; then
        info "Package database refresh and availability checks are skipped in dry-run."
        return 0
    fi

    validate_dns_resolution || return 1
    validate_internet_connection || return 1
    refresh_package_databases || return 1
    validate_configured_packages_available
}

install_base_system() {
    local -a packages=()
    mapfile -t packages < <(collect_packages)
    (( ${#packages[@]} > 0 )) || { error "No packages configured."; return 1; }
    run_command pacstrap -K "${MOUNT_ROOT}" "${packages[@]}"
}
