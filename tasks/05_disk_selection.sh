#!/usr/bin/env bash

task_disk_selection_name() { printf 'Disk selection'; }
task_disk_selection_validate() {
    validate_target_disk
}
task_disk_selection_execute() { show_target_disk_inspection; }
task_disk_selection_verify() { is_complete_disk "${TARGET_DISK}"; }
task_disk_selection_cleanup() { return 0; }
task_disk_selection_rollback() { return 0; }
