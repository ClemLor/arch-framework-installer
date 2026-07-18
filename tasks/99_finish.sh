#!/usr/bin/env bash

task_finish_name() { printf 'Finish'; }
task_finish_validate() { return 0; }
task_finish_execute() { success "Workflow completed. Review ${LOG_FILE} before rebooting."; }
task_finish_verify() { return 0; }
task_finish_cleanup() { return 0; }
task_finish_rollback() { return 0; }
