#!/usr/bin/env bash

# ==============================================================================
# Module: validation
#
# Purpose:
#   Validate the installation environment before any destructive operation.
#
# Idempotent:
#   Yes
# ==============================================================================

if [[ -n "${ARCH_INSTALLER_VALIDATION_LOADED:-}" ]]; then
    return 0
fi

readonly ARCH_INSTALLER_VALIDATION_LOADED="true"

validate_root_user() {
    if ! is_root; then
        error "The installer must be run as root."
        return 1
    fi

    success "Root privileges detected."
}

validate_architecture() {
    local architecture

    architecture="$(uname -m)"

    if [[ "${architecture}" != "x86_64" ]]; then
        error "Unsupported architecture: ${architecture}"
        return 1
    fi

    success "Supported architecture detected: ${architecture}."
}

validate_uefi() {
    local platform_size

    if ! is_uefi_system; then
        error "UEFI firmware data is unavailable at /sys/firmware/efi."
        error "Boot the USB entry prefixed with 'UEFI:' and disable Legacy/CSM mode."
        error "On the Arch ISO, verify with: cat /sys/firmware/efi/fw_platform_size"
        return 1
    fi

    platform_size="$(get_uefi_platform_size)"
    if [[ "${platform_size}" == "32" ]]; then
        error "A 32-bit UEFI was detected; this installer deploys the 64-bit BOOTX64.EFI loader."
        return 1
    fi

    success "UEFI mode detected (firmware platform size: ${platform_size})."
}

validate_target_disk() {
    if [[ ! -b "${TARGET_DISK}" ]]; then
        error "Target disk does not exist: ${TARGET_DISK}"
        return 1
    fi

    if [[ "$(lsblk -dn -o TYPE "${TARGET_DISK}" 2>/dev/null)" != "disk" ]]; then
        error "Target device is not a complete disk: ${TARGET_DISK}"
        return 1
    fi

    success "Target disk detected: ${TARGET_DISK}."
}

get_mounted_target_devices() {
    lsblk -nrpo NAME,MOUNTPOINT "${TARGET_DISK}" |
        awk 'NF > 1 && $2 != "" { print $1 " -> " $2 }'
}

validate_target_disk_not_mounted() {
    local mounted_devices

    mounted_devices="$(get_mounted_target_devices)"

    if [[ -z "${mounted_devices}" ]]; then
        success "No mounted filesystem detected on the target disk."
        return 0
    fi

    if [[ "${DRY_RUN:-false}" == "true" ]]; then
        warn "The target disk or one of its partitions is mounted."
        warn "This is accepted because dry-run mode is enabled."
        printf '%s\n' "${mounted_devices}" >&2
        return 0
    fi

    error "The target disk or one of its partitions is mounted:"
    printf '%s\n' "${mounted_devices}" >&2
    return 1
}

validate_required_commands() {
    local missing_commands=()
    local required_commands=(
        awk
        findmnt
        grep
        lsblk
        sed
    )
    local required_command

    for required_command in "${required_commands[@]}"; do
        if ! command_exists "${required_command}"; then
            missing_commands+=("${required_command}")
        fi
    done

    if (( ${#missing_commands[@]} > 0 )); then
        error "Missing required commands: ${missing_commands[*]}"
        return 1
    fi

    success "Required base commands are available."
}

validate_dns_resolution() {
    if ! command_exists getent; then
        warn "The getent command is unavailable; DNS validation was skipped."
        return 0
    fi

    if ! getent ahosts archlinux.org >/dev/null 2>&1; then
        error "DNS resolution failed for archlinux.org."
        return 1
    fi

    success "DNS resolution is working."
}

validate_internet_connection() {
    if command_exists curl; then
        if curl \
            --fail \
            --silent \
            --show-error \
            --location \
            --connect-timeout 5 \
            --max-time 10 \
            --output /dev/null \
            https://archlinux.org/; then
            success "Internet connection detected through HTTPS."
            return 0
        fi

        error "Unable to reach archlinux.org through HTTPS."
        return 1
    fi

    if command_exists wget; then
        if wget \
            --quiet \
            --timeout=10 \
            --spider \
            https://archlinux.org/; then
            success "Internet connection detected through HTTPS."
            return 0
        fi

        error "Unable to reach archlinux.org through HTTPS."
        return 1
    fi

    if command_exists ping; then
        warn "curl and wget are unavailable; using ping as a fallback."

        if ping -c 1 -W 3 archlinux.org >/dev/null 2>&1; then
            success "Internet connection detected through ICMP."
            return 0
        fi

        error "Unable to reach archlinux.org."
        return 1
    fi

    error "Cannot test the Internet connection: curl, wget and ping are unavailable."
    return 1
}

validate_environment() {
    section "Environment validation"

    local validation_failed="false"

    validate_root_user || validation_failed="true"
    validate_architecture || validation_failed="true"
    validate_uefi || validation_failed="true"
    validate_required_commands || validation_failed="true"
    validate_target_disk || validation_failed="true"
    validate_target_disk_not_mounted || validation_failed="true"
    validate_dns_resolution || validation_failed="true"
    validate_internet_connection || validation_failed="true"

    if [[ "${validation_failed}" == "true" ]]; then
        fatal "Environment validation failed."
    fi

    success "Environment validation completed."
}
