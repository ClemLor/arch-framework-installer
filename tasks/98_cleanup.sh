#!/usr/bin/env bash

task_cleanup_name() { printf 'Installation cleanup'; }
task_cleanup_validate() { return 0; }
task_cleanup_execute() { unmount_target_filesystems && close_luks_mapping; }
task_cleanup_verify() {
    [[ "${DRY_RUN}" == "true" ]] && return 0
    mountpoint -q "${MOUNT_ROOT}" && return 1
    [[ "${LUKS_ENABLED}" != "true" ]] || [[ ! -e "$(luks_mapping_path)" ]]
}
task_cleanup_cleanup() { return 0; }
task_cleanup_rollback() { return 0; }
