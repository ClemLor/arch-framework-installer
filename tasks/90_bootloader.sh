#!/usr/bin/env bash

task_bootloader_name() { printf 'Limine bootloader'; }
task_bootloader_validate() { [[ "${BOOTLOADER}" == "limine" ]]; }
task_bootloader_execute() { install_limine; }
task_bootloader_verify() { verify_limine; }
task_bootloader_cleanup() { return 0; }
task_bootloader_rollback() { return 0; }
