#!/usr/bin/env bash

task_encryption_name() { printf 'LUKS2 encryption'; }
task_encryption_validate() {
    [[ "${LUKS_ENABLED}" == "true" ]] || { error "This profile requires LUKS."; return 1; }
    validate_luks_dependencies || return 1
    [[ "${DRY_RUN}" == "true" ]] && return 0
    confirm_destructive_action "$(luks_device)" "Formatting $(luks_device) as LUKS2 is irreversible."
}
task_encryption_execute() { format_and_open_luks; }
task_encryption_verify() { verify_luks; }
task_encryption_cleanup() { return 0; }
task_encryption_rollback() { close_luks_mapping; }
