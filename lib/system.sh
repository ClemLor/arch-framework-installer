#!/usr/bin/env bash

# ==============================================================================
# Module: system
#
# Purpose:
#   Inspect the host system and the Arch Linux live environment without making
#   any modification.
#
# Idempotent:
#   Yes
# ==============================================================================

if [[ -n "${ARCH_INSTALLER_SYSTEM_LOADED:-}" ]]; then
    return 0
fi

readonly ARCH_INSTALLER_SYSTEM_LOADED="true"

read_first_existing_file() {
    local file_path

    for file_path in "$@"; do
        if [[ -r "${file_path}" ]]; then
            trim "$(<"${file_path}")"
            return 0
        fi
    done

    return 1
}

get_system_vendor() {
    read_first_existing_file \
        /sys/class/dmi/id/sys_vendor \
        /sys/devices/virtual/dmi/id/sys_vendor ||
        printf '%s' "Unknown"
}

get_system_product_name() {
    read_first_existing_file \
        /sys/class/dmi/id/product_name \
        /sys/devices/virtual/dmi/id/product_name ||
        printf '%s' "Unknown"
}

get_system_product_version() {
    read_first_existing_file \
        /sys/class/dmi/id/product_version \
        /sys/devices/virtual/dmi/id/product_version ||
        printf '%s' "Unknown"
}

get_firmware_vendor() {
    read_first_existing_file \
        /sys/class/dmi/id/bios_vendor \
        /sys/devices/virtual/dmi/id/bios_vendor ||
        printf '%s' "Unknown"
}

get_firmware_version() {
    read_first_existing_file \
        /sys/class/dmi/id/bios_version \
        /sys/devices/virtual/dmi/id/bios_version ||
        printf '%s' "Unknown"
}

get_cpu_model() {
    local cpu_model

    if command_exists lscpu; then
        cpu_model="$(
            lscpu |
                awk -F: '
                    $1 ~ /^Model name/ {
                        sub(/^[[:space:]]+/, "", $2)
                        print $2
                        exit
                    }
                '
        )"

        if [[ -n "${cpu_model}" ]]; then
            printf '%s' "${cpu_model}"
            return 0
        fi
    fi

    cpu_model="$(
        awk -F: '
            /^model name/ {
                sub(/^[[:space:]]+/, "", $2)
                print $2
                exit
            }
        ' /proc/cpuinfo 2>/dev/null
    )"

    if [[ -n "${cpu_model}" ]]; then
        printf '%s' "${cpu_model}"
    else
        printf '%s' "Unknown"
    fi
}

get_memory_bytes() {
    local memory_kib

    memory_kib="$(
        awk '
            /^MemTotal:/ {
                print $2
                exit
            }
        ' /proc/meminfo 2>/dev/null
    )"

    if [[ -z "${memory_kib}" ]]; then
        printf '%s' "0"
        return 1
    fi

    printf '%s' "$((memory_kib * 1024))"
}

format_bytes() {
    local bytes="${1:-0}"

    awk -v bytes="${bytes}" '
        function human(value) {
            if (value >= 1099511627776) {
                return sprintf("%.2f TiB", value / 1099511627776)
            }

            if (value >= 1073741824) {
                return sprintf("%.2f GiB", value / 1073741824)
            }

            if (value >= 1048576) {
                return sprintf("%.2f MiB", value / 1048576)
            }

            if (value >= 1024) {
                return sprintf("%.2f KiB", value / 1024)
            }

            return sprintf("%d B", value)
        }

        BEGIN {
            print human(bytes)
        }
    '
}

get_memory_human() {
    format_bytes "$(get_memory_bytes)"
}

get_kernel_version() {
    uname -r
}

get_current_architecture() {
    uname -m
}

get_boot_mode() {
    if is_uefi_system; then
        printf '%s' "UEFI"
    else
        printf '%s' "Legacy BIOS"
    fi
}

is_archiso_live_environment() {
    if [[ -d /run/archiso ]]; then
        return 0
    fi

    if [[ -e /etc/arch-release ]] &&
        findmnt -rn -o FSTYPE / 2>/dev/null |
            grep -Eq '^(overlay|squashfs)$'; then
        return 0
    fi

    return 1
}

get_environment_type() {
    if is_archiso_live_environment; then
        printf '%s' "Arch Linux live ISO"
    else
        printf '%s' "Installed or unsupported environment"
    fi
}

get_archiso_version() {
    local version_file
    local version_value

    for version_file in \
        /run/archiso/bootmnt/version \
        /run/archiso/bootmnt/arch/version \
        /version; do
        if [[ -r "${version_file}" ]]; then
            version_value="$(trim "$(<"${version_file}")")"

            if [[ -n "${version_value}" ]]; then
                printf '%s' "${version_value}"
                return 0
            fi
        fi
    done

    if command_exists pacman; then
        version_value="$(
            pacman -Q archlinux-keyring 2>/dev/null |
                awk '{ print $2 }'
        )"

        if [[ -n "${version_value}" ]]; then
            printf '%s' "Unknown ISO version (keyring ${version_value})"
            return 0
        fi
    fi

    printf '%s' "Unknown"
}

get_secure_boot_state() {
    local secure_boot_file
    local secure_boot_value

    if ! is_uefi_system; then
        printf '%s' "Unavailable"
        return 0
    fi

    secure_boot_file="$(
        find /sys/firmware/efi/efivars \
            -maxdepth 1 \
            -type f \
            -name 'SecureBoot-*' \
            -print \
            -quit 2>/dev/null
    )"

    if [[ -z "${secure_boot_file}" ]] || [[ ! -r "${secure_boot_file}" ]]; then
        printf '%s' "Unknown"
        return 0
    fi

    secure_boot_value="$(
        od \
            --address-radix=n \
            --format=u1 \
            --skip-bytes=4 \
            --read-bytes=1 \
            "${secure_boot_file}" 2>/dev/null |
            tr -d '[:space:]'
    )"

    case "${secure_boot_value}" in
        1)
            printf '%s' "Enabled"
            ;;
        0)
            printf '%s' "Disabled"
            ;;
        *)
            printf '%s' "Unknown"
            ;;
    esac
}

get_network_state() {
    if ! command_exists ip; then
        printf '%s' "Unknown"
        return 0
    fi

    if ip route show default 2>/dev/null | grep -q '^default '; then
        printf '%s' "Default route available"
    else
        printf '%s' "No default route"
    fi
}

get_tpm2_device() {
    local device_root="${TPM_DEVICE_ROOT:-/dev}"
    local device

    for device in "${device_root}/tpmrm0" "${device_root}/tpm0"; do
        if [[ -e "${device}" ]]; then
            printf '%s' "${device}"
            return 0
        fi
    done

    return 1
}

get_tpm_version_major() {
    local tpm_sysfs_root="${TPM_SYSFS_ROOT:-/sys/class/tpm}"
    local version_file="${tpm_sysfs_root}/tpm0/tpm_version_major"

    if [[ -r "${version_file}" ]]; then
        trim "$(<"${version_file}")"
    else
        printf '%s' "unknown"
    fi
}

has_tpm2_device() {
    local version

    get_tpm2_device >/dev/null || return 1
    version="$(get_tpm_version_major)"
    [[ "${version}" == "2" || "${version}" == "unknown" ]]
}

validate_live_environment() {
    if is_archiso_live_environment; then
        success "Arch Linux live environment detected."
        return 0
    fi

    if [[ "${DRY_RUN:-false}" == "true" ]] ||
        [[ "${INSPECT_MODE:-false}" == "true" ]]; then
        warn "The current system is not detected as the Arch Linux live ISO."
        warn "Dry-run and inspection are allowed, but a real installation must run from the live ISO."
        return 0
    fi

    error "The installer must run from the official Arch Linux live environment."
    return 1
}

show_system_inspection() {
    local product
    local product_version

    product="$(get_system_product_name)"
    product_version="$(get_system_product_version)"

    if [[ "${product_version}" != "Unknown" ]] &&
        [[ "${product_version}" != "${product}" ]]; then
        product="${product} ${product_version}"
    fi

    section "Host system"

    printf '%-20s %s\n' "Environment:" "$(get_environment_type)"
    printf '%-20s %s\n' "Arch ISO version:" "$(get_archiso_version)"
    printf '%-20s %s\n' "System vendor:" "$(get_system_vendor)"
    printf '%-20s %s\n' "Machine:" "${product}"
    printf '%-20s %s\n' "CPU:" "$(get_cpu_model)"
    printf '%-20s %s\n' "Memory:" "$(get_memory_human)"
    printf '%-20s %s\n' "Architecture:" "$(get_current_architecture)"
    printf '%-20s %s\n' "Kernel:" "$(get_kernel_version)"
    printf '%-20s %s\n' "Boot mode:" "$(get_boot_mode)"
    printf '%-20s %s\n' "Secure Boot:" "$(get_secure_boot_state)"
    printf '%-20s %s\n' "Firmware vendor:" "$(get_firmware_vendor)"
    printf '%-20s %s\n' "Firmware version:" "$(get_firmware_version)"
    printf '%-20s %s\n' "Network:" "$(get_network_state)"
}

configure_installed_system() {
    local locale_content
    locale_content="${LOCALE} UTF-8
${SECONDARY_LOCALE} UTF-8
"
    run_in_chroot ln -sf "/usr/share/zoneinfo/${TIMEZONE}" /etc/localtime || return 1
    run_in_chroot hwclock --systohc || return 1
    write_target_file /etc/locale.gen "${locale_content}" || return 1
    run_in_chroot locale-gen || return 1
    write_target_file /etc/locale.conf "LANG=${LOCALE}
" || return 1
    write_target_file /etc/vconsole.conf "KEYMAP=${KEYMAP}
" || return 1
    write_target_file /etc/hostname "${HOSTNAME}
" || return 1
    write_target_file /etc/hosts "127.0.0.1 localhost
::1 localhost
127.0.1.1 ${HOSTNAME}.localdomain ${HOSTNAME}
"
}
