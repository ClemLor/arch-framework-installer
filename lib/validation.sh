```bash
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
}

validate_architecture() {
    if ! is_architecture_supported; then
        error "Unsupported architecture: $(uname -m)"
        return 1
    fi
}

validate_uefi() {
    if ! is_uefi_system; then
        error "The system was not booted in UEFI mode."
        return 1
    fi
}

validate_target_disk() {
    if [[ ! -b "${TARGET_DISK}" ]]; then
        error "Target disk does not exist: ${TARGET_DISK}"
        return 1
    fi

    if findmnt -rn -S "${TARGET_DISK}" >/dev/null 2>&1; then
        error "Target disk is currently mounted: ${TARGET_DISK}"
        return 1
    fi
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
}

validate_internet_connection() {
    if ! ping -c 1 -W 3 archlinux.org >/dev/null 2>&1; then
        error "No Internet connection detected."
        return 1
    fi
}

validate_environment() {
    section "Environment validation"

    local validation_failed="false"

    validate_root_user || validation_failed="true"
    validate_architecture || validation_failed="true"
    validate_uefi || validation_failed="true"
    validate_required_commands || validation_failed="true"
    validate_target_disk || validation_failed="true"
    validate_internet_connection || validation_failed="true"

    if [[ "${validation_failed}" == "true" ]]; then
        fatal "Environment validation failed."
    fi

    success "Environment validation completed."
}
```
