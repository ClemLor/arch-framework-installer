#!/usr/bin/env bash

if [[ -n "${ARCH_INSTALLER_BTRFS_LOADED:-}" ]]; then return 0; fi
readonly ARCH_INSTALLER_BTRFS_LOADED="true"

BTRFS_LABEL="${BTRFS_LABEL:-ARCHROOT}"

validate_btrfs_dependencies() {
    require_commands_for_mode "Btrfs" mkfs.btrfs btrfs mount umount blkid mountpoint
}

create_btrfs_layout() {
    local device
    local temporary_mount
    local subvolume
    device="$(luks_mapping_path)"
    temporary_mount="${MOUNT_ROOT}/.btrfs-root"

    run_command mkfs.btrfs --force --label "${BTRFS_LABEL}" "${device}" || return 1
    run_command mkdir -p "${temporary_mount}" || return 1
    run_command mount "${device}" "${temporary_mount}" || return 1
    for subvolume in "${BTRFS_SUBVOLUMES[@]}"; do
        run_command btrfs subvolume create "${temporary_mount}/${subvolume}" || return 1
    done
    run_command umount "${temporary_mount}"
}

verify_btrfs_layout() {
    local device
    local temporary_mount
    local subvolume
    [[ "${DRY_RUN:-false}" == "true" ]] && return 0
    device="$(luks_mapping_path)"
    temporary_mount="${MOUNT_ROOT}/.btrfs-verify"
    [[ "$(blkid -s TYPE -o value "${device}")" == "btrfs" ]] || return 1
    mkdir -p "${temporary_mount}" || return 1
    mount -o ro,subvolid=5 "${device}" "${temporary_mount}" || return 1
    for subvolume in "${BTRFS_SUBVOLUMES[@]}"; do
        if ! btrfs subvolume show "${temporary_mount}/${subvolume}" >/dev/null; then
            umount "${temporary_mount}" || true
            return 1
        fi
    done
    umount "${temporary_mount}"
}

cleanup_btrfs_temporary_mounts() {
    local path
    [[ "${DRY_RUN:-false}" == "true" ]] && return 0
    for path in "${MOUNT_ROOT}/.btrfs-verify" "${MOUNT_ROOT}/.btrfs-root"; do
        if mountpoint -q "${path}"; then
            run_command umount "${path}" || return 1
        fi
    done
}
