#!/usr/bin/env bash

task_filesystem_name() { printf 'Btrfs filesystem'; }
task_filesystem_validate() {
    validate_btrfs_dependencies || return 1
    require_commands_for_mode "EFI filesystem" mkfs.fat
}
task_filesystem_execute() { create_btrfs_layout && run_command mkfs.fat -F 32 -n "${EFI_PARTITION_LABEL}" "$(get_efi_partition_path)"; }
task_filesystem_verify() {
    [[ "${DRY_RUN}" == "true" ]] && return 0
    verify_btrfs_layout && [[ "$(blkid -s TYPE -o value "$(get_efi_partition_path)")" == "vfat" ]]
}
task_filesystem_cleanup() { cleanup_btrfs_temporary_mounts; }
task_filesystem_rollback() { return 0; }
