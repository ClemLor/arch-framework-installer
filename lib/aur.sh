#!/usr/bin/env bash

# ==============================================================================
# Module: aur
#
# Purpose:
#   Install the helper script that sets up AUR software after the first boot.
#
# Nothing here builds anything. AUR packages are never passed to pacstrap: the
# live ISO has no build environment and no unprivileged user, makepkg refuses to
# run as root, and a failed build during installation could roll back a system
# that was otherwise complete and bootable.
#
# So the installer writes a script and the user runs it once, logged in, with the
# build output in front of them. A broken PKGBUILD is then an inconvenience
# rather than a failed installation.
#
# Idempotent:
#   Yes
# ==============================================================================

if [[ -n "${ARCH_INSTALLER_AUR_LOADED:-}" ]]; then return 0; fi
readonly ARCH_INSTALLER_AUR_LOADED="true"

readonly AUR_SETUP_PATH='/usr/local/bin/afi-aur-setup'
readonly AUR_SHARE_DIRECTORY='/usr/local/share/arch-framework-installer'
readonly AUR_LIST_PATH="${AUR_SHARE_DIRECTORY}/aur.list"

# Built from source rather than paru-bin: no prebuilt binary to trust, and cargo
# is worth having on a development machine anyway.
readonly AUR_HELPER='paru'
readonly AUR_HELPER_REPOSITORY='https://aur.archlinux.org/paru.git'

# The packages to install after reboot.
#
# AUR_PACKAGES from the configuration wins when set, so the menu can offer the
# list as checkboxes. An unset variable means the whole of packages/aur.list,
# which keeps a hand-edited configuration working. An explicitly empty array
# means the user deselected everything, and is honoured.
selected_aur_packages() {
    local list
    list="$(project_root)/packages/aur.list"

    if [[ -n "${AUR_PACKAGES+x}" ]]; then
        (( ${#AUR_PACKAGES[@]} == 0 )) && return 0
        printf '%s\n' "${AUR_PACKAGES[@]}"
        return
    fi

    [[ -s "${list}" ]] || return 0
    read_package_list "${list}"
}

configure_aur_setup() {
    local packages

    packages="$(selected_aur_packages)"

    if [[ -z "${packages}" ]]; then
        info "No AUR packages selected; the setup script is still installed for later."
    fi

    # The list has to live on the target: the repository will not be there after
    # a reboot, and the script must remain useful for retries and later additions.
    write_target_file "${AUR_LIST_PATH}" "${packages}
" || return 1

    write_aur_setup_script || return 1

    run_command chmod 0755 "${MOUNT_ROOT}${AUR_SETUP_PATH}"
}

write_aur_setup_script() {
    write_target_file "${AUR_SETUP_PATH}" '#!/usr/bin/env bash
# Installed by arch-framework-installer.
#
# Bootstraps an AUR helper, then installs the packages recorded at
# /usr/local/share/arch-framework-installer/aur.list.
#
# Run it once, as your normal user, after the first boot. Re-running it is safe:
# it skips whatever is already installed.

set -Eeuo pipefail

readonly LIST="'"${AUR_LIST_PATH}"'"
readonly HELPER="'"${AUR_HELPER}"'"
readonly REPOSITORY="'"${AUR_HELPER_REPOSITORY}"'"

info() { printf "\033[0;34m[INFO]\033[0m %s\n" "$*"; }
warn() { printf "\033[0;33m[WARN]\033[0m %s\n" "$*" >&2; }
fail() { printf "\033[0;31m[ERROR]\033[0m %s\n" "$*" >&2; exit 1; }

# makepkg refuses to run as root, and building as root would leave root-owned
# files in the build tree even if it did not.
if [[ "${EUID}" -eq 0 ]]; then
    fail "Run this as your normal user, not with sudo. makepkg refuses to run as root."
fi

command -v sudo >/dev/null || fail "sudo is required."
command -v git >/dev/null || fail "git is required to clone the helper PKGBUILD."
command -v makepkg >/dev/null || fail "base-devel is required (makepkg is missing)."

# Asked for once, up front, rather than in the middle of a long build where a
# timed-out prompt would abandon it.
info "Checking sudo access; you may be asked for your password."
sudo --validate || fail "sudo access is required to install packages."

bootstrap_helper() {
    local build_directory

    if command -v "${HELPER}" >/dev/null; then
        info "${HELPER} is already installed."
        return 0
    fi

    info "Building ${HELPER} from the AUR. This pulls the Rust toolchain and takes a few minutes."
    build_directory="$(mktemp --directory)"
    # Left in place on failure so the build log can be read.
    git clone --depth 1 "${REPOSITORY}" "${build_directory}/${HELPER}" ||
        fail "Could not clone ${REPOSITORY}."

    ( cd "${build_directory}/${HELPER}" && makepkg --syncdeps --install --noconfirm ) ||
        fail "${HELPER} failed to build. The tree is at ${build_directory}."

    rm -rf "${build_directory}"
    info "${HELPER} installed."
}

install_packages() {
    local -a packages=()
    local -a failed=()
    local package

    [[ -r "${LIST}" ]] || fail "Package list not found: ${LIST}"
    mapfile -t packages < <(sed -e "s/[[:space:]]*#.*$//" -e "/^[[:space:]]*$/d" "${LIST}")

    if (( ${#packages[@]} == 0 )); then
        info "No AUR packages are configured."
        return 0
    fi

    # One at a time on purpose. A single --needed invocation aborts the whole set
    # when one PKGBUILD is broken, which is common enough that it would routinely
    # leave most of the list uninstalled.
    for package in "${packages[@]}"; do
        info "Installing ${package}"
        if ! "${HELPER}" --sync --needed --noconfirm "${package}"; then
            warn "${package} failed to install."
            failed+=("${package}")
        fi
    done

    if (( ${#failed[@]} > 0 )); then
        warn "These packages did not install: ${failed[*]}"
        warn "Re-run this script to retry, or build them by hand to see why."
        return 1
    fi

    info "All configured AUR packages are installed."
}

bootstrap_helper
install_packages
'
}

verify_aur_setup() {
    [[ "${DRY_RUN:-false}" == "true" ]] && return 0

    verify_target_file "${AUR_SETUP_PATH}" || {
        error "The AUR setup script is missing."
        return 1
    }

    [[ -x "${MOUNT_ROOT}${AUR_SETUP_PATH}" ]] || {
        error "The AUR setup script is not executable."
        return 1
    }

    verify_target_file "${AUR_LIST_PATH}" || {
        error "The AUR package list was not copied into the target."
        return 1
    }

    # The script cannot bootstrap anything without these, and discovering that
    # after a reboot is worse than discovering it now.
    local requirement
    for requirement in git sudo base-devel; do
        run_in_chroot pacman -Q "${requirement}" >/dev/null || {
            error "${requirement} is missing; afi-aur-setup could not build anything."
            return 1
        }
    done
}
