#!/usr/bin/env bash

# ==============================================================================
# Module: disk
#
# Purpose:
#   Inspect block devices, identify the Arch live medium and validate the target
#   installation disk without modifying storage.
#
# Idempotent:
#   Yes
# ==============================================================================

if [[ -n "${ARCH_INSTALLER_DISK_LOADED:-}" ]]; then
    return 0
fi

readonly ARCH_INSTALLER_DISK_LOADED="true"

normalize_block_device() {
    local device="${1:-}"

    if [[ -z "${device}" ]]; then
        return 1
    fi

    if [[ "${device}" == /dev/* ]] && command_exists readlink; then
        readlink -f "${device}" 2>/dev/null || printf '%s' "${device}"
        return 0
    fi

    printf '%s' "${device}"
}

get_block_property() {
    local device="$1"
    local property="$2"

    lsblk \
        --nodeps \
        --noheadings \
        --bytes \
        --output "${property}" \
        "${device}" 2>/dev/null |
        head -n 1 |
        sed 's/^[[:space:]]*//;s/[[:space:]]*$//'
}

get_disk_model() {
    local model

    model="$(get_block_property "$1" MODEL)"

    if [[ -n "${model}" ]]; then
        printf '%s' "${model}"
    else
        printf '%s' "Unknown"
    fi
}

get_disk_serial() {
    local serial

    serial="$(get_block_property "$1" SERIAL)"

    if [[ -n "${serial}" ]]; then
        printf '%s' "${serial}"
    else
        printf '%s' "Unknown"
    fi
}

get_disk_size_bytes() {
    local size

    size="$(get_block_property "$1" SIZE)"

    if [[ "${size}" =~ ^[0-9]+$ ]]; then
        printf '%s' "${size}"
    else
        printf '%s' "0"
    fi
}

get_disk_transport() {
    local transport

    transport="$(get_block_property "$1" TRAN)"

    if [[ -n "${transport}" ]]; then
        printf '%s' "${transport}"
    elif [[ "$1" == /dev/nvme* ]]; then
        printf '%s' "nvme"
    else
        printf '%s' "Unknown"
    fi
}

get_disk_removable_state() {
    local removable

    removable="$(get_block_property "$1" RM)"

    case "${removable}" in
        1)
            printf '%s' "yes"
            ;;
        0)
            printf '%s' "no"
            ;;
        *)
            printf '%s' "unknown"
            ;;
    esac
}

get_disk_rotational_state() {
    local rotational

    rotational="$(get_block_property "$1" ROTA)"

    case "${rotational}" in
        1)
            printf '%s' "rotational"
            ;;
        0)
            printf '%s' "solid-state"
            ;;
        *)
            printf '%s' "unknown"
            ;;
    esac
}

get_disk_partition_table() {
    local partition_table

    partition_table="$(get_block_property "$1" PTTYPE)"

    if [[ -n "${partition_table}" ]]; then
        printf '%s' "${partition_table}"
    else
        printf '%s' "none"
    fi
}

get_disk_logical_sector_size() {
    local sector_size

    sector_size="$(get_block_property "$1" LOG-SEC)"

    if [[ -n "${sector_size}" ]]; then
        printf '%s' "${sector_size}"
    else
        printf '%s' "Unknown"
    fi
}

get_disk_physical_sector_size() {
    local sector_size

    sector_size="$(get_block_property "$1" PHY-SEC)"

    if [[ -n "${sector_size}" ]]; then
        printf '%s' "${sector_size}"
    else
        printf '%s' "Unknown"
    fi
}

get_disk_mounts() {
    local disk="$1"

    lsblk \
        --raw \
        --noheadings \
        --paths \
        --output NAME,MOUNTPOINTS \
        "${disk}" 2>/dev/null |
        awk '
            NF >= 2 {
                device = $1
                $1 = ""
                sub(/^[[:space:]]+/, "", $0)

                if ($0 != "") {
                    print device " -> " $0
                }
            }
        '
}

disk_has_mounted_filesystems() {
    [[ -n "$(get_disk_mounts "$1")" ]]
}

get_disk_encryption_state() {
    local disk="$1"

    if lsblk \
        --raw \
        --noheadings \
        --output FSTYPE \
        "${disk}" 2>/dev/null |
        grep -qx 'crypto_LUKS'; then
        printf '%s' "LUKS detected"
    else
        printf '%s' "not detected"
    fi
}

get_parent_block_device() {
    local device="$1"
    local parent_name

    parent_name="$(
        lsblk \
            --nodeps \
            --noheadings \
            --output PKNAME \
            "${device}" 2>/dev/null |
            head -n 1 |
            tr -d '[:space:]'
    )"

    if [[ -n "${parent_name}" ]]; then
        printf '/dev/%s' "${parent_name}"
        return 0
    fi

    return 1
}

resolve_parent_disk() {
    local current_device
    local current_type
    local parent_device
    local iteration=0

    current_device="$(normalize_block_device "$1")"

    while [[ -n "${current_device}" ]] && ((iteration < 16)); do
        current_type="$(
            lsblk \
                --nodeps \
                --noheadings \
                --output TYPE \
                "${current_device}" 2>/dev/null |
                head -n 1 |
                tr -d '[:space:]'
        )"

        if [[ "${current_type}" == "disk" ]]; then
            printf '%s' "${current_device}"
            return 0
        fi

        parent_device="$(get_parent_block_device "${current_device}" || true)"

        if [[ -z "${parent_device}" ]] ||
            [[ "${parent_device}" == "${current_device}" ]]; then
            break
        fi

        current_device="$(normalize_block_device "${parent_device}")"
        ((iteration += 1))
    done

    return 1
}

get_mount_source() {
    local mountpoint="$1"

    findmnt \
        --noheadings \
        --raw \
        --output SOURCE \
        --target "${mountpoint}" 2>/dev/null |
        head -n 1
}

get_live_medium_source() {
    local mountpoint
    local source

    for mountpoint in \
        /run/archiso/bootmnt \
        /run/archiso/cowspace \
        /run/archiso; do
        if [[ ! -e "${mountpoint}" ]]; then
            continue
        fi

        source="$(get_mount_source "${mountpoint}")"

        if [[ "${source}" == /dev/* ]]; then
            normalize_block_device "${source}"
            return 0
        fi
    done

    source="$(get_mount_source /)"

    if [[ "${source}" == /dev/* ]]; then
        normalize_block_device "${source}"
        return 0
    fi

    return 1
}

get_live_medium_disk() {
    local source

    source="$(get_live_medium_source || true)"

    if [[ -z "${source}" ]]; then
        return 1
    fi

    resolve_parent_disk "${source}"
}

is_live_medium_disk() {
    local candidate
    local live_disk

    candidate="$(normalize_block_device "$1")"
    live_disk="$(get_live_medium_disk || true)"

    [[ -n "${live_disk}" ]] && [[ "${candidate}" == "${live_disk}" ]]
}

is_usb_disk() {
    [[ "$(get_disk_transport "$1")" == "usb" ]]
}

is_removable_disk() {
    [[ "$(get_disk_removable_state "$1")" == "yes" ]]
}

is_complete_disk() {
    local device_type

    device_type="$(
        lsblk \
            --nodeps \
            --noheadings \
            --output TYPE \
            "$1" 2>/dev/null |
            head -n 1 |
            tr -d '[:space:]'
    )"

    [[ "${device_type}" == "disk" ]]
}

is_installation_candidate() {
    local disk="$1"

    is_complete_disk "${disk}" || return 1
    is_live_medium_disk "${disk}" && return 1
    is_usb_disk "${disk}" && return 1
    is_removable_disk "${disk}" && return 1

    return 0
}

list_all_disks() {
    lsblk \
        --disk \
        --noheadings \
        --paths \
        --output NAME 2>/dev/null |
        sed '/^[[:space:]]*$/d'
}

list_installation_candidates() {
    local disk

    while IFS= read -r disk; do
        [[ -n "${disk}" ]] || continue

        if is_installation_candidate "${disk}"; then
            printf '%s\n' "${disk}"
        fi
    done < <(list_all_disks)
}

get_disk_safety_status() {
    local disk="$1"

    if ! is_complete_disk "${disk}"; then
        printf '%s' "Rejected: not a complete disk"
        return 0
    fi

    if is_live_medium_disk "${disk}"; then
        printf '%s' "Rejected: Arch live medium"
        return 0
    fi

    if is_usb_disk "${disk}"; then
        printf '%s' "Rejected: USB transport"
        return 0
    fi

    if is_removable_disk "${disk}"; then
        printf '%s' "Rejected: removable device"
        return 0
    fi

    if disk_has_mounted_filesystems "${disk}"; then
        if [[ "${DRY_RUN:-false}" == "true" ]] ||
            [[ "${INSPECT_MODE:-false}" == "true" ]]; then
            printf '%s' "Warning: mounted filesystems"
        else
            printf '%s' "Rejected: mounted filesystems"
        fi

        return 0
    fi

    printf '%s' "Eligible"
}

show_live_medium_inspection() {
    local source
    local disk

    source="$(get_live_medium_source || true)"
    disk="$(get_live_medium_disk || true)"

    section "Live installation medium"

    if [[ -n "${source}" ]]; then
        printf '%-20s %s\n' "Mounted source:" "${source}"
    else
        printf '%-20s %s\n' "Mounted source:" "Not detected"
    fi

    if [[ -n "${disk}" ]]; then
        printf '%-20s %s\n' "Physical disk:" "${disk}"
        printf '%-20s %s\n' "Model:" "$(get_disk_model "${disk}")"
        printf '%-20s %s\n' "Transport:" "$(get_disk_transport "${disk}")"
        printf '%-20s %s\n' "Removable:" "$(get_disk_removable_state "${disk}")"
    else
        printf '%-20s %s\n' "Physical disk:" "Not detected"
    fi
}

show_target_disk_inspection() {
    local disk="${TARGET_DISK}"
    local mounts
    local size_bytes

    section "Configured target disk"

    if [[ ! -b "${disk}" ]]; then
        printf '%-20s %s\n' "Device:" "${disk}"
        printf '%-20s %s\n' "Status:" "Device not found"
        return 0
    fi

    size_bytes="$(get_disk_size_bytes "${disk}")"
    mounts="$(get_disk_mounts "${disk}")"

    printf '%-20s %s\n' "Device:" "${disk}"
    printf '%-20s %s\n' "Model:" "$(get_disk_model "${disk}")"
    printf '%-20s %s\n' "Serial:" "$(get_disk_serial "${disk}")"
    printf '%-20s %s\n' "Size:" "$(format_bytes "${size_bytes}")"
    printf '%-20s %s\n' "Transport:" "$(get_disk_transport "${disk}")"
    printf '%-20s %s\n' "Storage type:" "$(get_disk_rotational_state "${disk}")"
    printf '%-20s %s\n' "Removable:" "$(get_disk_removable_state "${disk}")"
    printf '%-20s %s\n' "Partition table:" "$(get_disk_partition_table "${disk}")"
    printf '%-20s %s\n' "Encryption:" "$(get_disk_encryption_state "${disk}")"
    printf '%-20s %s\n' "Logical sector:" "$(get_disk_logical_sector_size "${disk}") bytes"
    printf '%-20s %s\n' "Physical sector:" "$(get_disk_physical_sector_size "${disk}") bytes"
    printf '%-20s %s\n' "Safety status:" "$(get_disk_safety_status "${disk}")"

    if [[ -n "${mounts}" ]]; then
        printf '%-20s\n' "Mounted filesystems:"
        printf '%s\n' "${mounts}" |
            sed 's/^/  /'
    else
        printf '%-20s %s\n' "Mounted filesystems:" "none"
    fi
}

show_installation_candidates() {
    local candidates
    local disk
    local size_bytes

    candidates="$(list_installation_candidates)"

    section "Internal installation candidates"

    if [[ -z "${candidates}" ]]; then
        printf '%s\n' "No eligible internal disk detected."
        return 0
    fi

    while IFS= read -r disk; do
        [[ -n "${disk}" ]] || continue

        size_bytes="$(get_disk_size_bytes "${disk}")"

        printf '%s\n' "${disk}"
        printf '  %-18s %s\n' "Model:" "$(get_disk_model "${disk}")"
        printf '  %-18s %s\n' "Size:" "$(format_bytes "${size_bytes}")"
        printf '  %-18s %s\n' "Transport:" "$(get_disk_transport "${disk}")"
        printf '  %-18s %s\n' "Status:" "$(get_disk_safety_status "${disk}")"
    done <<<"${candidates}"
}

show_all_disk_summary() {
    local disk
    local size_bytes

    section "All detected disks"

    while IFS= read -r disk; do
        [[ -n "${disk}" ]] || continue

        size_bytes="$(get_disk_size_bytes "${disk}")"

        printf '%s\n' "${disk}"
        printf '  %-18s %s\n' "Model:" "$(get_disk_model "${disk}")"
        printf '  %-18s %s\n' "Size:" "$(format_bytes "${size_bytes}")"
        printf '  %-18s %s\n' "Transport:" "$(get_disk_transport "${disk}")"
        printf '  %-18s %s\n' "Removable:" "$(get_disk_removable_state "${disk}")"
        printf '  %-18s %s\n' "Classification:" "$(get_disk_safety_status "${disk}")"
    done < <(list_all_disks)
}

show_disk_inspection() {
    show_live_medium_inspection
    show_target_disk_inspection
    show_installation_candidates
    show_all_disk_summary
}
