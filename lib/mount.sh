#!/usr/bin/env bash

if [[ -n "${ARCH_INSTALLER_MOUNT_LOADED:-}" ]]; then return 0; fi
readonly ARCH_INSTALLER_MOUNT_LOADED="true"

btrfs_mount_options() { printf 'noatime,compress=%s:%s,ssd,space_cache=v2' "${BTRFS_COMPRESSION}" "${BTRFS_COMPRESSION_LEVEL}"; }

mount_target_filesystems() {
    local device
    local options
    device="$(root_block_device)"
    options="$(btrfs_mount_options)"
    run_command mkdir -p "${MOUNT_ROOT}" || return 1
    run_command mount -o "${options},subvol=@" "${device}" "${MOUNT_ROOT}" || return 1
    run_command mkdir -p "${MOUNT_ROOT}/home" "${MOUNT_ROOT}/.snapshots" "${MOUNT_ROOT}/var/cache" "${MOUNT_ROOT}/var/log" "${MOUNT_ROOT}/boot" || return 1
    run_command mount -o "${options},subvol=@home" "${device}" "${MOUNT_ROOT}/home" || return 1
    run_command mount -o "${options},subvol=@snapshots" "${device}" "${MOUNT_ROOT}/.snapshots" || return 1
    run_command mount -o "${options},subvol=@cache" "${device}" "${MOUNT_ROOT}/var/cache" || return 1
    run_command mount -o "${options},subvol=@log" "${device}" "${MOUNT_ROOT}/var/log" || return 1
    run_command mount "$(get_efi_partition_path)" "${MOUNT_ROOT}/boot"
}

unmount_target_filesystems() {
    [[ "${DRY_RUN:-false}" == "true" ]] && return 0
    if mountpoint -q "${MOUNT_ROOT}"; then
        run_command umount -R "${MOUNT_ROOT}"
    fi
}

verify_target_mounts() {
    [[ "${DRY_RUN:-false}" == "true" ]] && return 0
    findmnt --mountpoint "${MOUNT_ROOT}" >/dev/null && findmnt --mountpoint "${MOUNT_ROOT}/boot" >/dev/null
}
