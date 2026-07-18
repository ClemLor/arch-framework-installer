#!/usr/bin/env bash

STORAGE_CONFIRMED="false"
task_storage_name() { printf 'GPT partitioning'; }
task_storage_validate() {
    validate_storage_plan || return 1
    [[ "${DRY_RUN}" == "true" ]] && return 0
    show_storage_plan
    confirm_destructive_action "${TARGET_DISK}" "All data on ${TARGET_DISK} will be permanently destroyed." || { error "Destructive confirmation rejected."; return 1; }
    STORAGE_CONFIRMED="true"
}
task_storage_execute() {
    show_planned_partition_layout
    [[ "${DRY_RUN}" == "true" || "${STORAGE_CONFIRMED}" == "true" ]] || return 1
    create_partition_table && wait_for_partition_devices
}
task_storage_verify() { verify_partition_table; }
task_storage_cleanup() { [[ "${DRY_RUN}" == "true" ]] || run_command udevadm settle; }
task_storage_rollback() { warn "Partitioning is irreversible; previous data is never restored automatically."; return 0; }
