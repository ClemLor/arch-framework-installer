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

validate_size_value() {
    local variable_name="$1"
    local value="${!variable_name:-}"

    if [[ ! "${value}" =~ ^[0-9]+(MiB|GiB|TiB)$ ]]; then
        error "${variable_name} must use the format 1024MiB, 32GiB or 1TiB."
        return 1
    fi
}

validate_partition_label() {
    local variable_name="$1"
    local value="${!variable_name:-}"

    if [[ ! "${value}" =~ ^[A-Za-z0-9_-]+$ ]]; then
        error "${variable_name} may contain only letters, numbers, underscores and hyphens."
        return 1
    fi
}

validate_hostname() {
    local label
    local value="${HOSTNAME:-}"
    local -a labels=()

    if [[ ${#value} -gt 253 ]] ||
        [[ ! "${value}" =~ ^[A-Za-z0-9]([A-Za-z0-9.-]*[A-Za-z0-9])?$ ]] ||
        [[ "${value}" == *..* ]]; then
        error "HOSTNAME must be a valid DNS hostname."
        return 1
    fi

    IFS='.' read -r -a labels <<<"${value}"
    for label in "${labels[@]}"; do
        if [[ ${#label} -gt 63 ]] || [[ ! "${label}" =~ ^[A-Za-z0-9]([A-Za-z0-9-]*[A-Za-z0-9])?$ ]]; then
            error "Each HOSTNAME label must be valid and 63 characters or fewer."
            return 1
        fi
    done
}

validate_timezone() {
    local zoneinfo_root="${ZONEINFO_ROOT:-/usr/share/zoneinfo}"

    if [[ ! "${TIMEZONE:-}" =~ ^(UTC|[A-Za-z0-9_+-]+(/[A-Za-z0-9_+-]+)+)$ ]] ||
        [[ ! -f "${zoneinfo_root}/${TIMEZONE:-}" ]]; then
        error "TIMEZONE must name an existing zoneinfo file."
        return 1
    fi
}

validate_identity_configuration() {
    local user_groups="${USER_GROUPS:-}"
    local user_name="${USERNAME:-}"
    local user_shell="${USER_SHELL:-}"

    if [[ ! "${user_name}" =~ ^[a-z_][a-z0-9_-]*$ ]]; then
        error "USERNAME is not a valid Linux account name."
        return 1
    fi

    if [[ ! "${user_shell}" =~ ^/[A-Za-z0-9_./+-]+$ ]] || [[ "${user_shell}" == *..* ]]; then
        error "USER_SHELL must be a safe absolute path."
        return 1
    fi

    if [[ ! "${user_groups}" =~ ^[a-z_][a-z0-9_-]*(,[a-z_][a-z0-9_-]*)*$ ]]; then
        error "USER_GROUPS must be a comma-separated list of valid group names."
        return 1
    fi
}

validate_locale_configuration() {
    local value

    for value in "${LOCALE:-}" "${SECONDARY_LOCALE:-}"; do
        if [[ ! "${value}" =~ ^[A-Za-z][A-Za-z0-9_@.-]*$ ]]; then
            error "LOCALE and SECONDARY_LOCALE contain an invalid value."
            return 1
        fi
    done

    if [[ ! "${KEYMAP:-}" =~ ^[A-Za-z0-9_-]+$ ]]; then
        error "KEYMAP contains an invalid value."
        return 1
    fi
}

validate_btrfs_subvolumes() {
    if [[ -z "${BTRFS_SUBVOLUMES+x}" ]]; then
        error "Missing configuration array: BTRFS_SUBVOLUMES"
        return 1
    fi

    if (( ${#BTRFS_SUBVOLUMES[@]} == 0 )); then
        error "BTRFS_SUBVOLUMES must contain at least one subvolume."
        return 1
    fi

    local required_subvolumes=(
        "@"
        "@home"
        "@snapshots"
        "@cache"
        "@log"
    )
    local required_subvolume
    local configured_subvolume
    local found

    for required_subvolume in "${required_subvolumes[@]}"; do
        found="false"

        for configured_subvolume in "${BTRFS_SUBVOLUMES[@]}"; do
            if [[ "${configured_subvolume}" == "${required_subvolume}" ]]; then
                found="true"
                break
            fi
        done

        if [[ "${found}" != "true" ]]; then
            error "Missing required Btrfs subvolume: ${required_subvolume}"
            return 1
        fi
    done
}

validate_config() {
    local has_error="false"
    local variable_name

    local required_variables=(
        HOSTNAME
        TIMEZONE
        LOCALE
        SECONDARY_LOCALE
        KEYMAP
        XKB_LAYOUT
        XKB_VARIANT
        TARGET_DISK
        EFI_SIZE
        EFI_PARTITION_LABEL
        SYSTEM_PARTITION_LABEL
        MINIMUM_DISK_SIZE
        LUKS_NAME
        FILESYSTEM
        BTRFS_COMPRESSION
        BTRFS_COMPRESSION_LEVEL
        SWAP_SIZE
        DEFAULT_KERNEL
        FALLBACK_KERNEL
        BOOTLOADER
        MOUNT_ROOT
        USERNAME
        USER_SHELL
        USER_GROUPS
        DESKTOP_COMPOSITOR
        DESKTOP_SHELL
    )

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
        ENABLE_REAL_INSTALLATION
        DESKTOP_AUTOLOGIN
        DMS_LOCK_ON_START
    )

    for variable_name in "${boolean_variables[@]}"; do
        if ! validate_boolean "${variable_name}"; then
            has_error="true"
        fi
    done

    local size_variables=(
        EFI_SIZE
        MINIMUM_DISK_SIZE
        SWAP_SIZE
    )

    for variable_name in "${size_variables[@]}"; do
        if ! validate_size_value "${variable_name}"; then
            has_error="true"
        fi
    done

    local partition_label_variables=(
        EFI_PARTITION_LABEL
        SYSTEM_PARTITION_LABEL
    )

    for variable_name in "${partition_label_variables[@]}"; do
        if ! validate_partition_label "${variable_name}"; then
            has_error="true"
        fi
    done

    if ! validate_hostname; then
        has_error="true"
    fi

    if ! validate_timezone; then
        has_error="true"
    fi

    if ! validate_identity_configuration; then
        has_error="true"
    fi

    if ! validate_locale_configuration; then
        has_error="true"
    fi

    if [[ "${TARGET_DISK}" != /dev/* ]]; then
        error "TARGET_DISK must be an absolute device path under /dev."
        has_error="true"
    fi

    if [[ "${FILESYSTEM}" != "btrfs" ]]; then
        error "Only Btrfs is currently supported."
        has_error="true"
    fi

    if [[ "${BOOTLOADER}" != "limine" ]]; then
        error "Only Limine is currently supported."
        has_error="true"
    fi

    if [[ "${DESKTOP_COMPOSITOR}" != "niri" ]] || [[ "${DESKTOP_SHELL}" != "dank" ]]; then
        error "The supported desktop profile is niri with dank."
        has_error="true"
    fi

    if [[ "${DESKTOP_AUTOLOGIN}" == "true" ]] && [[ "${DMS_LOCK_ON_START}" != "true" ]]; then
        error "DESKTOP_AUTOLOGIN=true requires DMS_LOCK_ON_START=true."
        has_error="true"
    fi

    if [[ "${MOUNT_ROOT}" != /* ]] || [[ "${MOUNT_ROOT}" == "/" ]]; then
        error "MOUNT_ROOT must be an absolute path other than /."
        has_error="true"
    fi

    if [[ "${LUKS_ENABLED}" != "true" ]] && [[ "${TPM2_ENABLED}" == "true" ]]; then
        error "TPM2_ENABLED requires LUKS_ENABLED=true."
        has_error="true"
    fi

    if [[ "${SWAP_SIZE}" != "0MiB" ]] && [[ "${SWAP_SIZE}" != "0GiB" ]]; then
        error "Disk swap is unsupported; SWAP_SIZE must be 0MiB or 0GiB (zram is used)."
        has_error="true"
    fi

    if [[ "${HIBERNATION_ENABLED}" == "true" ]]; then
        error "Hibernation requires persistent swap and is not supported by the zram-only design."
        has_error="true"
    fi

    if [[ ! "${BTRFS_COMPRESSION_LEVEL}" =~ ^[0-9]+$ ]]; then
        error "BTRFS_COMPRESSION_LEVEL must be a positive integer."
        has_error="true"
    fi

    if ! validate_btrfs_subvolumes; then
        has_error="true"
    fi

    if [[ "${has_error}" == "true" ]]; then
        fatal "Configuration validation failed."
    fi

    success "Configuration is valid."
}
