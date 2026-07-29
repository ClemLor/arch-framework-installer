#!/usr/bin/env bash

task_mount_name() { printf 'Target mounts'; }
task_mount_validate() {
    require_commands_for_mode "Mounts" findmnt mount mountpoint umount || return 1
    validate_swap_dependencies || return 1
    validate_swap_size_for_hibernation
}
task_mount_execute() { mount_target_filesystems && create_swapfile; }
task_mount_verify() { verify_target_mounts && verify_swapfile; }
task_mount_cleanup() { return 0; }
task_mount_rollback() { unmount_target_filesystems; }
