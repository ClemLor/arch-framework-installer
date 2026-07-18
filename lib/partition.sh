#!/usr/bin/env bash

# ==============================================================================
# Module: partition
#
# Purpose:
#   Validate and display the planned GPT partition layout without modifying the
#   target disk.
#
# Current behavior:
#   Planning and inspection only.
#
# Idempotent:
#   Yes
# ==============================================================================

if [[ -n "${ARCH_INSTALLER_PARTITION_LOADED:-}" ]]; then
    return 0
fi

readonly ARCH_INSTALLER_PARTITION_LOADED="true"

size_to_mib() {
    local value="$1"
    local number
    local unit

    if [[ ! "${value}" =~ ^([1-9][0-9]*)(MiB|GiB|TiB)$ ]]; then
        error "Unsupported size value: ${value}"
        return 1
    fi

    number="${BASH_REMATCH[1]}"
    unit="${BASH_REMATCH[2]}"

    case "${unit}" in
        MiB)
            printf '%s' "${number}"
            ;;
        GiB)
            printf '%s' "$((number * 1024))"
            ;;
        TiB)
            printf '%s' "$((number * 1024 * 1024))"
            ;;
        *)
            return 1
            ;;
    esac
}

size_to_bytes() {
    local size_mib

    size_mib="$(size_to_mib "$1")" || return 1

    printf '%s' "$((size_mib * 1024 * 1024))"
}

get_partition_path() {
    local disk="$1"
    local partition_number="$2"

    case "${disk}" in
        /dev/nvme* | /dev/mmcblk* | /dev/loop*)
            printf '%sp%s' "${disk}" "${partition_number}"
            ;;
        *)
            printf '%s%s' "${disk}" "${partition_number}"
            ;;
    esac
}

get_efi_partition_path() {
    get_partition_path "${TARGET_DISK}" 1
}

get_system_partition_path() {
    get_partition_path "${TARGET_DISK}" 2
}

get_efi_end_mib() {
    local efi_size_mib

    efi_size_mib="$(size_to_mib "${EFI_SIZE}")" || return 1

    # The first partition starts at 1 MiB for alignment.
    printf '%s' "$((efi_size_mib + 1))"
}

validate_partition_dependencies() {
    local required_commands=(
        lsblk
        sgdisk
        wipefs
        partprobe
        udevadm
    )
    require_commands_for_mode "Storage" "${required_commands[@]}" || return 1

    success "Storage planning commands are available."
}

create_partition_table() {
    local efi_end_mib
    efi_end_mib="$(get_efi_end_mib)" || return 1

    run_command wipefs --all "${TARGET_DISK}" || return 1
    run_command sgdisk --zap-all "${TARGET_DISK}" || return 1
    run_command sgdisk \
        --new="1:1MiB:${efi_end_mib}MiB" \
        --typecode="1:ef00" \
        --change-name="1:${EFI_PARTITION_LABEL}" \
        "${TARGET_DISK}" || return 1
    run_command sgdisk \
        --new="2:0:0" \
        --typecode="2:8309" \
        --change-name="2:${SYSTEM_PARTITION_LABEL}" \
        "${TARGET_DISK}" || return 1
    run_command partprobe "${TARGET_DISK}" || return 1
    run_command udevadm settle || return 1
}

wait_for_partition_devices() {
    local attempt
    local efi_partition
    local system_partition

    [[ "${DRY_RUN:-false}" == "true" ]] && return 0
    efi_partition="$(get_efi_partition_path)"
    system_partition="$(get_system_partition_path)"

    for ((attempt=0; attempt<20; attempt++)); do
        if [[ -b "${efi_partition}" ]] && [[ -b "${system_partition}" ]]; then
            return 0
        fi
        sleep 1
    done

    error "Partition devices did not appear within 20 seconds."
    return 1
}

verify_partition_table() {
    local efi_partition
    local system_partition
    local partition_count
    local efi_type
    local system_type
    local disk_size_bytes
    local efi_size_bytes
    local system_size_bytes
    local expected_efi_size_bytes
    local unallocated_bytes

    [[ "${DRY_RUN:-false}" == "true" ]] && return 0
    efi_partition="$(get_efi_partition_path)"
    system_partition="$(get_system_partition_path)"

    sgdisk --verify "${TARGET_DISK}" >/dev/null || return 1
    [[ "$(get_disk_partition_table "${TARGET_DISK}")" == "gpt" ]] || return 1
    partition_count="$(get_disk_partition_count "${TARGET_DISK}")"
    [[ "${partition_count}" -eq 2 ]] || return 1

    efi_type="$(get_partition_type_guid "${efi_partition}")"
    system_type="$(get_partition_type_guid "${system_partition}")"
    [[ "${efi_type,,}" == "c12a7328-f81f-11d2-ba4b-00a0c93ec93b" ]] || return 1
    [[ "${system_type,,}" == "ca7d7ccb-63ed-4c53-861c-1742536059cc" ]] || return 1
    [[ "$(get_partition_label "${efi_partition}")" == "${EFI_PARTITION_LABEL}" ]] || return 1
    [[ "$(get_partition_label "${system_partition}")" == "${SYSTEM_PARTITION_LABEL}" ]] || return 1

    disk_size_bytes="$(get_disk_size_bytes "${TARGET_DISK}")"
    efi_size_bytes="$(get_disk_size_bytes "${efi_partition}")"
    system_size_bytes="$(get_disk_size_bytes "${system_partition}")"
    expected_efi_size_bytes="$(size_to_bytes "${EFI_SIZE}")" || return 1
    (( efi_size_bytes >= expected_efi_size_bytes - 1048576 )) || return 1
    (( efi_size_bytes <= expected_efi_size_bytes + 1048576 )) || return 1
    (( efi_size_bytes + system_size_bytes <= disk_size_bytes )) || return 1
    unallocated_bytes=$((disk_size_bytes - efi_size_bytes - system_size_bytes))
    (( unallocated_bytes <= 4194304 )) || return 1
    is_partition_mib_aligned "${efi_partition}" || return 1
    is_partition_mib_aligned "${system_partition}" || return 1
}

validate_target_disk_capacity() {
    local disk_size_bytes
    local minimum_size_bytes

    disk_size_bytes="$(get_disk_size_bytes "${TARGET_DISK}")"
    minimum_size_bytes="$(size_to_bytes "${MINIMUM_DISK_SIZE}")"

    if [[ ! "${disk_size_bytes}" =~ ^[0-9]+$ ]] ||
        ((disk_size_bytes == 0)); then
        error "Unable to determine the target disk size."
        return 1
    fi

    if ((disk_size_bytes < minimum_size_bytes)); then
        error "The target disk is too small."
        error "Detected: $(format_bytes "${disk_size_bytes}")"
        error "Required: ${MINIMUM_DISK_SIZE}"
        return 1
    fi

    success "Target disk capacity is sufficient."
}

validate_efi_partition_size() {
    local efi_size_mib

    efi_size_mib="$(size_to_mib "${EFI_SIZE}")" || return 1

    if ((efi_size_mib < 512)); then
        error "EFI_SIZE must be at least 512MiB."
        return 1
    fi

    if ((efi_size_mib > 4096)); then
        error "EFI_SIZE must not exceed 4GiB."
        return 1
    fi

    success "EFI partition size is valid."
}

validate_partition_target_safety() {
    if [[ ! -b "${TARGET_DISK}" ]]; then
        error "Target disk does not exist: ${TARGET_DISK}"
        return 1
    fi

    if ! is_complete_disk "${TARGET_DISK}"; then
        error "Target device is not a complete disk: ${TARGET_DISK}"
        return 1
    fi

    if is_live_medium_disk "${TARGET_DISK}"; then
        error "The target disk is the active Arch Linux live medium."
        return 1
    fi

    if is_usb_disk "${TARGET_DISK}"; then
        error "USB disks cannot be used as installation targets."
        return 1
    fi

    if is_removable_disk "${TARGET_DISK}"; then
        error "Removable disks cannot be used as installation targets."
        return 1
    fi

    if disk_has_mounted_filesystems "${TARGET_DISK}"; then
        if [[ "${DRY_RUN:-false}" == "true" ]] ||
            [[ "${INSPECT_MODE:-false}" == "true" ]] ||
            [[ "${STORAGE_PLAN_MODE:-false}" == "true" ]]; then
            warn "The target disk currently contains mounted filesystems."
            warn "This is accepted because only a read-only storage plan is being generated."
            return 0
        fi

        error "The target disk or one of its partitions is mounted."
        return 1
    fi

    success "Target disk passed the storage safety checks."
}

validate_storage_plan() {
    section "Storage plan validation"

    local validation_failed="false"

    validate_partition_dependencies || validation_failed="true"
    validate_partition_target_safety || validation_failed="true"
    validate_target_disk_capacity || validation_failed="true"
    validate_efi_partition_size || validation_failed="true"

    if [[ "${validation_failed}" == "true" ]]; then
        error "Storage plan validation failed."
        return 1
    fi

    success "Storage plan validation completed."
}

show_existing_partition_layout() {
    section "Existing target layout"

    if ! lsblk \
        --paths \
        --output NAME,SIZE,TYPE,FSTYPE,PARTTYPENAME,MOUNTPOINTS \
        "${TARGET_DISK}"; then
        warn "Unable to display the current partition layout."
    fi
}

show_planned_partition_layout() {
    local efi_partition
    local system_partition
    local efi_end_mib
    local disk_size_bytes

    efi_partition="$(get_efi_partition_path)"
    system_partition="$(get_system_partition_path)"
    efi_end_mib="$(get_efi_end_mib)"
    disk_size_bytes="$(get_disk_size_bytes "${TARGET_DISK}")"

    section "Planned GPT layout"

    printf '%-22s %s\n' "Target disk:" "${TARGET_DISK}"
    printf '%-22s %s\n' "Disk model:" "$(get_disk_model "${TARGET_DISK}")"
    printf '%-22s %s\n' "Disk size:" "$(format_bytes "${disk_size_bytes}")"
    printf '%-22s %s\n' "Partition table:" "GPT"
    printf '\n'

    printf '%-5s %-22s %-14s %-14s %-14s %s\n' \
        "#" "Device" "Start" "End" "Filesystem" "Purpose"

    printf '%-5s %-22s %-14s %-14s %-14s %s\n' \
        "1" \
        "${efi_partition}" \
        "1MiB" \
        "${efi_end_mib}MiB" \
        "FAT32" \
        "EFI System Partition"

    printf '%-5s %-22s %-14s %-14s %-14s %s\n' \
        "2" \
        "${system_partition}" \
        "next aligned" \
        "100%" \
        "LUKS2" \
        "Encrypted Arch system"

    printf '\n'
    printf '%-22s %s\n' "EFI label:" "${EFI_PARTITION_LABEL}"
    printf '%-22s %s\n' "System label:" "${SYSTEM_PARTITION_LABEL}"
    printf '%-22s %s\n' "LUKS mapping:" "/dev/mapper/${LUKS_NAME}"
    printf '%-22s %s\n' "Inner filesystem:" "${FILESYSTEM}"
}

show_partition_commands() {
    local efi_end_mib

    efi_end_mib="$(get_efi_end_mib)"

    section "Planned destructive commands"

    warn "The following commands are displayed for review only."
    warn "They are not executed by the current implementation."

    printf '\n'

    printf 'wipefs --all %q\n' "${TARGET_DISK}"
    printf 'sgdisk --zap-all %q\n' "${TARGET_DISK}"

    printf 'sgdisk --new=1:1MiB:%sMiB --typecode=1:ef00 --change-name=1:%q %q\n' \
        "${efi_end_mib}" \
        "${EFI_PARTITION_LABEL}" \
        "${TARGET_DISK}"

    printf 'sgdisk --new=2:0:0 --typecode=2:8309 --change-name=2:%q %q\n' \
        "${SYSTEM_PARTITION_LABEL}" \
        "${TARGET_DISK}"

    printf 'partprobe %q\n' "${TARGET_DISK}"
}

show_storage_plan() {
    validate_storage_plan
    show_existing_partition_layout
    show_planned_partition_layout
    show_partition_commands

    section "Storage plan result"

    success "The storage plan was generated without modifying the target disk."
}
