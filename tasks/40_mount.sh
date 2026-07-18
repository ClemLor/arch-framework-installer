#!/usr/bin/env bash

task_mount_name() { printf 'Target mounts'; }
task_mount_validate() { require_commands_for_mode "Mounts" findmnt mount mountpoint umount; }
task_mount_execute() { mount_target_filesystems; }
task_mount_verify() { verify_target_mounts; }
task_mount_cleanup() { return 0; }
task_mount_rollback() { unmount_target_filesystems; }
