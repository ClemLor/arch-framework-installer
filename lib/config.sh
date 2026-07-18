```bash
#!/usr/bin/env bash

# ==============================================================================
# Module: config
#
# Purpose:
#   Load and validate the installer configuration.
#
# Inputs:
#   config/system.conf
#
# Idempotent:
#   Yes
# ==============================================================================

if [[ -n "${ARCH_INSTALLER_CONFIG_LOADED:-}" ]]; then
    return 0
fi

readonly ARCH_INSTALLER_CONFIG_LOADED="true"

CONFIG_FILE="${CONFIG_FILE:-}"

load_config() {
    local root

    root="$(project_root)"

    if [[ -z "${CONFIG_FILE}" ]]; then
        CONFIG_FILE="${root}/config/system.conf"
    fi

    if [[ ! -f "${CONFIG_FILE}" ]]; then
        fatal "Configuration file not found: ${CONFIG_FILE}"
    fi

    info "Loading configuration from ${CONFIG_FILE}"

    # shellcheck source=/dev/null
    source "${CONFIG_FILE}"

    validate_config
}

require_config_variable() {
    local variable_name="$1"

    if [[ -z "${!variable_name+x}" ]]; then
        error "Missing configuration variable: ${variable_name}"
        return 1
    fi

    if [[ -z "${!variable_name}" ]]; then
        error "Empty configuration variable: ${variable_name}"
        return 1
    fi
}

validate_boolean() {
    local variable_name="$1"
    local value="${!variable_name:-}"

    case "${value}" in
        true | false)
            return 0
            ;;
        *)
            error "${variable_name} must be true or false."
            return 1
            ;;
    esac
}

validate_config() {
    local has_error="false"

    local required_variables=(
        HOSTNAME
        TIMEZONE
        LOCALE
        KEYMAP
        TARGET_DISK
        EFI_SIZE
        LUKS_NAME
        FILESYSTEM
        SWAP_SIZE
        DEFAULT_KERNEL
        BOOTLOADER
    )

    local variable_name

    for variable_name in "${required_variables[@]}"; do
        if ! require_config_variable "${variable_name}"; then
            has_error="true"
        fi
    done

    local boolean_variables=(
        LUKS_ENABLED
        TPM2_ENABLED
        ZRAM_ENABLED
        HIBERNATION_ENABLED
        DRY_RUN
        INTERACTIVE_CONFIRMATION
    )

    for variable_name in "${boolean_variables[@]}"; do
        if ! validate_boolean "${variable_name}"; then
            has_error="true"
        fi
    done

    if [[ "${FILESYSTEM}" != "btrfs" ]]; then
        error "Only Btrfs is currently supported."
        has_error="true"
    fi

    if [[ "${BOOTLOADER}" != "limine" ]]; then
        error "Only Limine is currently supported."
        has_error="true"
    fi

    if [[ "${has_error}" == "true" ]]; then
        fatal "Configuration validation failed."
    fi

    success "Configuration is valid."
}
```
