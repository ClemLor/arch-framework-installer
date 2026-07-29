#!/usr/bin/env bash

# Names no bootloader. The implementation is chosen by BOOTLOADER and dispatched
# through lib/provider.sh, so adding one does not touch this file.

task_bootloader_name() { bootloader_display_name; }
task_bootloader_validate() {
    validate_bootloader_provider || return 1
    require_commands_for_mode "Bootloader" arch-chroot blkid
}
task_bootloader_execute() { bootloader_install; }
task_bootloader_verify() { bootloader_verify; }
task_bootloader_cleanup() { return 0; }
task_bootloader_rollback() { return 0; }
