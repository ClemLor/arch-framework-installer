#!/usr/bin/env bash

task_base_system_name() { printf 'Base system'; }
task_base_system_validate() {
    require_commands_for_mode "Base installation" pacstrap || return 1
    [[ -s "$(project_root)/packages/base.list" ]] || return 1
    if [[ "${DRY_RUN}" == "true" ]]; then
        warn "Network availability is not required to render the dry-run plan."
        return 0
    fi
    validate_dns_resolution && validate_internet_connection
}
task_base_system_execute() { install_base_system; }
task_base_system_verify() { [[ "${DRY_RUN}" == "true" ]] || [[ -x "${MOUNT_ROOT}/usr/bin/pacman" ]]; }
task_base_system_cleanup() { return 0; }
task_base_system_rollback() { return 0; }
