#!/usr/bin/env bash

task_users_name() { printf 'Users'; }
task_users_validate() { [[ "${USERNAME}" =~ ^[a-z_][a-z0-9_-]*$ ]]; }
task_users_execute() {
    create_installed_user || return 1
    configure_user_desktop
}
task_users_verify() {
    [[ "${DRY_RUN}" == "true" ]] || {
        run_in_chroot id "${USERNAME}" >/dev/null && verify_user_desktop
    }
}
task_users_cleanup() { return 0; }
task_users_rollback() { return 0; }
