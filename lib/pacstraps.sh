#!/usr/bin/env bash

if [[ -n "${ARCH_INSTALLER_PACSTRAP_LOADED:-}" ]]; then return 0; fi
readonly ARCH_INSTALLER_PACSTRAP_LOADED="true"

read_package_list() {
    sed -e 's/[[:space:]]*#.*$//' -e '/^[[:space:]]*$/d' "$1"
}

# Every group that exists. base, firmware and framework are not optional: without
# them the result does not boot or cannot be repaired.
readonly AVAILABLE_PACKAGE_GROUPS=(
    base firmware framework desktop development fonts multimedia optional
)
readonly MANDATORY_PACKAGE_GROUPS=(base firmware framework)

# Groups to install. Overridable from the configuration, so the menu can offer
# them as checkboxes; unset means all of them, which is the previous behaviour.
selected_package_groups() {
    local group

    if [[ -n "${PACKAGE_GROUPS+x}" ]] && (( ${#PACKAGE_GROUPS[@]} > 0 )); then
        # Mandatory groups are added back rather than rejected: a configuration
        # that omits them is a mistake worth correcting, not worth aborting over.
        printf '%s\n' "${MANDATORY_PACKAGE_GROUPS[@]}" "${PACKAGE_GROUPS[@]}" |
            LC_ALL=C sort -u
        return
    fi

    for group in "${AVAILABLE_PACKAGE_GROUPS[@]}"; do
        printf '%s\n' "${group}"
    done
}

collect_packages() {
    local root
    local list
    root="$(project_root)"

    {
        while IFS= read -r list; do
            [[ -s "${root}/packages/${list}.list" ]] || continue
            read_package_list "${root}/packages/${list}.list"
        done < <(selected_package_groups)

        # Packages the chosen bootloader and desktop session require. Declared by
        # the providers so that swapping one swaps its packages with it, instead
        # of leaving the previous one's behind in a list nobody edits.
        bootloader_packages
        desktop_packages
    } | LC_ALL=C sort -u
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
