#!/usr/bin/env bash

task_readiness_name() { printf 'Final readiness'; }
task_readiness_validate() {
    require_commands_for_mode "Final readiness" arch-chroot findmnt grep
}
task_readiness_execute() { return 0; }
task_readiness_verify() { verify_installation_readiness; }
task_readiness_cleanup() { return 0; }
task_readiness_rollback() { return 0; }
