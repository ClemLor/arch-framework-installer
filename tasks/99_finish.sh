#!/usr/bin/env bash

# ==============================================================================
# Task: finish
#
# Purpose:
#   Install Paru in the target system after all other installation tasks.
#
# Idempotent:
#   Yes
# ==============================================================================

set -Eeuo pipefail

install_paru_inside_target() {
    local builder_home="/tmp/paru-build"
    local builder_user="paru-build"
    local package_file
    local -a package_files=()

    if [[ "${EUID}" -ne 0 ]]; then
        printf 'Paru installation must run as root inside the target system.\n' >&2
        return 1
    fi

    if pacman -Q paru >/dev/null 2>&1; then
        printf '[OK] Paru is already installed.\n'
        return 0
    fi

    if id "${builder_user}" >/dev/null 2>&1; then
        printf 'Temporary build user already exists: %s\n' "${builder_user}" >&2
        return 1
    fi

    cleanup_paru_builder() {
        if id "${builder_user}" >/dev/null 2>&1; then
            userdel --remove "${builder_user}" >/dev/null 2>&1 || true
        fi
    }
    trap cleanup_paru_builder EXIT

    # AUR packages must be reviewed and built as an unprivileged user.
    pacman -S --needed --noconfirm -- base-devel git rust
    useradd --create-home --home-dir "${builder_home}" \
        --shell /usr/bin/nologin "${builder_user}"
    runuser -u "${builder_user}" -- \
        git clone --depth 1 https://aur.archlinux.org/paru.git \
        "${builder_home}/paru"
    runuser -u "${builder_user}" -- \
        env HOME="${builder_home}" bash -c \
        'cd "$HOME/paru" && makepkg --cleanbuild --noconfirm'

    while IFS= read -r package_file; do
        if [[ "${package_file##*/}" != paru-debug-* ]]; then
            package_files+=("${package_file}")
        fi
    done < <(
        runuser -u "${builder_user}" -- \
            env HOME="${builder_home}" bash -c \
            'cd "$HOME/paru" && makepkg --packagelist'
    )

    if (( ${#package_files[@]} == 0 )); then
        printf 'The Paru package was not produced.\n' >&2
        return 1
    fi

    pacman -U --needed --noconfirm -- "${package_files[@]}"
    printf '[OK] Paru installed successfully.\n'
}

if [[ "${1:-}" == "--inside-target" ]]; then
    install_paru_inside_target
    exit 0
fi

readonly TASK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly PROJECT_ROOT="$(cd "${TASK_DIR}/.." && pwd)"
readonly TARGET_ROOT="${TARGET_ROOT:-/mnt}"
readonly TARGET_SCRIPT="/tmp/arch-framework-install-paru.sh"

# shellcheck source=lib/logging.sh
source "${PROJECT_ROOT}/lib/logging.sh"

# shellcheck source=lib/common.sh
source "${PROJECT_ROOT}/lib/common.sh"

# shellcheck source=lib/commands.sh
source "${PROJECT_ROOT}/lib/commands.sh"

cleanup_target_script() {
    run_command rm -f -- "${TARGET_ROOT}${TARGET_SCRIPT}"
}

if [[ "${DRY_RUN}" != "true" ]]; then
    require_root
    command_exists arch-chroot || fatal "Missing required command: arch-chroot"
    [[ -d "${TARGET_ROOT}" ]] || fatal "Target root not found: ${TARGET_ROOT}"
fi

section "Final installation tasks"

trap cleanup_target_script EXIT
run_critical "Copying the Paru installer into the target system." \
    install -Dm755 -- "${BASH_SOURCE[0]}" "${TARGET_ROOT}${TARGET_SCRIPT}"
run_critical "Installing Paru in the target system." \
    arch-chroot "${TARGET_ROOT}" "${TARGET_SCRIPT}" --inside-target
cleanup_target_script
trap - EXIT

success "Final installation tasks completed."
