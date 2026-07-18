#!/usr/bin/env bash

# ==============================================================================
# Arch Framework Installer
#
# Purpose:
#   Orchestrate a reproducible Arch Linux installation on a Framework Laptop.
#
# Execution environment:
#   Official Arch Linux live ISO booted in UEFI mode.
#
# Idempotent:
#   Yes
# ==============================================================================

set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly SCRIPT_DIR

CLI_DRY_RUN="false"
CLI_VERBOSE="false"
INSPECT_MODE="false"
STORAGE_PLAN_MODE="false"
PARTITION_ONLY_MODE="false"

# shellcheck source=lib/logging.sh
source "${SCRIPT_DIR}/lib/logging.sh"

# shellcheck source=lib/common.sh
source "${SCRIPT_DIR}/lib/common.sh"

# shellcheck source=lib/commands.sh
source "${SCRIPT_DIR}/lib/commands.sh"

# shellcheck source=lib/config.sh
source "${SCRIPT_DIR}/lib/config.sh"

# shellcheck source=lib/ui.sh
source "${SCRIPT_DIR}/lib/ui.sh"

# shellcheck source=lib/system.sh
source "${SCRIPT_DIR}/lib/system.sh"

# shellcheck source=lib/disk.sh
source "${SCRIPT_DIR}/lib/disk.sh"

# shellcheck source=lib/partition.sh
source "${SCRIPT_DIR}/lib/partition.sh"

# shellcheck source=lib/validation.sh
source "${SCRIPT_DIR}/lib/validation.sh"

# shellcheck source=lib/state.sh
source "${SCRIPT_DIR}/lib/state.sh"
# shellcheck source=lib/progress.sh
source "${SCRIPT_DIR}/lib/progress.sh"
# shellcheck source=lib/luks.sh
source "${SCRIPT_DIR}/lib/luks.sh"
# shellcheck source=lib/btrfs.sh
source "${SCRIPT_DIR}/lib/btrfs.sh"
# shellcheck source=lib/mount.sh
source "${SCRIPT_DIR}/lib/mount.sh"
# shellcheck source=lib/chroot.sh
source "${SCRIPT_DIR}/lib/chroot.sh"
# shellcheck source=lib/pacstraps.sh
source "${SCRIPT_DIR}/lib/pacstraps.sh"
# shellcheck source=lib/packages.sh
source "${SCRIPT_DIR}/lib/packages.sh"
# shellcheck source=lib/services.sh
source "${SCRIPT_DIR}/lib/services.sh"
# shellcheck source=lib/desktop.sh
source "${SCRIPT_DIR}/lib/desktop.sh"
# shellcheck source=lib/snapshots.sh
source "${SCRIPT_DIR}/lib/snapshots.sh"
# shellcheck source=lib/memory.sh
source "${SCRIPT_DIR}/lib/memory.sh"
# shellcheck source=lib/users.sh
source "${SCRIPT_DIR}/lib/users.sh"
# shellcheck source=lib/bootloader.sh
source "${SCRIPT_DIR}/lib/bootloader.sh"
# shellcheck source=lib/verify.sh
source "${SCRIPT_DIR}/lib/verify.sh"
# shellcheck source=lib/hooks.sh
source "${SCRIPT_DIR}/lib/hooks.sh"
# shellcheck source=lib/task.sh
source "${SCRIPT_DIR}/lib/task.sh"

usage() {
    cat <<'EOF'
Usage:
  ./install.sh [options]

Options:
  --config FILE    Use an alternative configuration file.
  --dry-run        Display planned operations without changing the system.
  --inspect        Inspect the host and disks, then exit.
  --plan-storage   Validate and display the planned disk layout, then exit.
  --partition      Run tasks through real partitioning, then stop.
  --verbose        Display executed commands.
  --help           Display this help.

Examples:
  sudo ./install.sh --inspect
  sudo ./install.sh --inspect --dry-run
  sudo ./install.sh --plan-storage
  sudo ./install.sh --plan-storage --dry-run
  sudo ./install.sh --dry-run --verbose
EOF
}

parse_arguments() {
    while [[ "$#" -gt 0 ]]; do
        case "$1" in
            --config)
                if [[ "$#" -lt 2 ]]; then
                    fatal "--config requires a file path."
                fi

                CONFIG_FILE="$2"
                shift 2
                ;;
            --dry-run)
                CLI_DRY_RUN="true"
                shift
                ;;
            --inspect)
                INSPECT_MODE="true"
                shift
                ;;
            --plan-storage)
                STORAGE_PLAN_MODE="true"
                shift
                ;;
            --partition)
                PARTITION_ONLY_MODE="true"
                shift
                ;;
            --verbose)
                CLI_VERBOSE="true"
                shift
                ;;
            --help)
                usage
                exit 0
                ;;
            *)
                fatal "Unknown option: $1"
                ;;
        esac
    done
}

apply_cli_overrides() {
    if [[ "${CLI_DRY_RUN}" == "true" ]]; then
        DRY_RUN="true"
    fi

    if [[ "${CLI_VERBOSE}" == "true" ]]; then
        VERBOSE="true"
    fi
}

validate_execution_mode() {
    local selected_modes=0

    if [[ "${INSPECT_MODE}" == "true" ]]; then
        ((selected_modes += 1))
    fi

    if [[ "${STORAGE_PLAN_MODE}" == "true" ]]; then
        ((selected_modes += 1))
    fi

    if [[ "${PARTITION_ONLY_MODE}" == "true" ]]; then
        ((selected_modes += 1))
    fi

    if ((selected_modes > 1)); then
        fatal "--inspect, --plan-storage and --partition are mutually exclusive."
    fi
}

show_installation_summary() {
    section "Installation configuration"

    printf '%-22s %s\n' "Hostname:" "${HOSTNAME}"
    printf '%-22s %s\n' "Target disk:" "${TARGET_DISK}"
    printf '%-22s %s\n' "Minimum disk size:" "${MINIMUM_DISK_SIZE}"
    printf '%-22s %s\n' "EFI size:" "${EFI_SIZE}"
    printf '%-22s %s\n' "Filesystem:" "${FILESYSTEM}"
    printf '%-22s %s\n' "Compression:" "${BTRFS_COMPRESSION}:${BTRFS_COMPRESSION_LEVEL}"
    printf '%-22s %s\n' "Encryption:" "${LUKS_ENABLED}"
    printf '%-22s %s\n' "TPM2:" "${TPM2_ENABLED}"
    printf '%-22s %s\n' "Swap:" "${SWAP_SIZE}"
    printf '%-22s %s\n' "Zram:" "${ZRAM_ENABLED}"
    printf '%-22s %s\n' "Hibernation:" "${HIBERNATION_ENABLED}"
    printf '%-22s %s\n' "Bootloader:" "${BOOTLOADER}"
    printf '%-22s %s\n' "Default kernel:" "${DEFAULT_KERNEL}"
    printf '%-22s %s\n' "Fallback kernel:" "${FALLBACK_KERNEL}"
    printf '%-22s %s\n' "Desktop:" "${DESKTOP_COMPOSITOR} + ${DESKTOP_SHELL}"
    printf '%-22s %s\n' "Desktop auto-login:" "${DESKTOP_AUTOLOGIN}"
    printf '%-22s %s\n' "DMS lock on start:" "${DMS_LOCK_ON_START}"
    printf '%-22s %s\n' "Dry run:" "${DRY_RUN}"
}

inspect_system() {
    section "Arch Framework Installer inspection"

    show_system_inspection
    show_live_medium_inspection
    show_target_disk_inspection
    show_installation_candidates
    show_all_disk_summary
    show_installation_summary

    section "Inspection result"

    if is_archiso_live_environment; then
        success "Arch Linux live environment detected."
    else
        warn "Inspection completed outside the Arch Linux live environment."
    fi

    if [[ -b "${TARGET_DISK}" ]] &&
        is_installation_candidate "${TARGET_DISK}"; then
        success "The configured target is an eligible internal disk."
    elif [[ -b "${TARGET_DISK}" ]] &&
        [[ "${DRY_RUN}" == "true" ]] &&
        disk_has_mounted_filesystems "${TARGET_DISK}" &&
        ! is_live_medium_disk "${TARGET_DISK}" &&
        ! is_usb_disk "${TARGET_DISK}" &&
        ! is_removable_disk "${TARGET_DISK}"; then
        warn "The configured target is mounted but accepted for dry-run inspection."
    else
        warn "The configured target is not currently eligible for installation."
    fi

    success "Inspection completed without modifying the system."
}

main() {
    parse_arguments "$@"
    validate_execution_mode

    load_config
    apply_cli_overrides
    init_logging "${SCRIPT_DIR}"
    state_init "${SCRIPT_DIR}"

    if [[ "${INSPECT_MODE}" == "true" ]]; then
        inspect_system
        exit 0
    fi

    if [[ "${STORAGE_PLAN_MODE}" == "true" ]]; then
        show_storage_plan
        exit 0
    fi

    if [[ "${PARTITION_ONLY_MODE}" == "true" ]]; then
        TASK_STOP_AFTER="storage"
    fi

    if ! task_run_all "${SCRIPT_DIR}/tasks"; then
        error "Installation workflow failed. See ${LOG_FILE}."
        return 1
    fi

    success "Installation workflow completed. Log: ${LOG_FILE}"
}

main "$@"
