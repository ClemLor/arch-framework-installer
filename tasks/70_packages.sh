#!/usr/bin/env bash

task_packages_name() { printf 'Packages and services'; }
task_packages_validate() { [[ -s "$(project_root)/packages/desktop.list" ]]; }
task_packages_execute() { configure_services; }
task_packages_verify() {
    [[ "${DRY_RUN}" == "true" ]] || {
        verify_required_packages && verify_enabled_services
    }
}
task_packages_cleanup() { return 0; }
task_packages_rollback() { return 0; }
