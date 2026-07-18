#!/usr/bin/env bash

task_environment_name() { printf 'Environment'; }
task_environment_validate() {
    validate_live_environment || return 1
    if [[ "${DRY_RUN}" == "true" ]] && ! is_root; then
        warn "Root privileges are not required for dry-run; some device metadata may be unavailable."
    else
        validate_root_user || return 1
    fi
    validate_architecture || return 1
    if [[ "${DRY_RUN}" != "true" ]]; then validate_uefi || return 1; fi
    validate_required_commands || return 1
    require_commands_for_mode "Package preflight" pacman || return 1
    require_real_installation_enabled
}
task_environment_execute() {
    show_installation_summary
    prepare_package_sources
}
task_environment_verify() { [[ "${DRY_RUN}" == "true" ]] || is_archiso_live_environment; }
task_environment_cleanup() { return 0; }
task_environment_rollback() { return 0; }
