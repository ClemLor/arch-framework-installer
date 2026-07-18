#!/usr/bin/env bash

if [[ -n "${ARCH_INSTALLER_HOOKS_LOADED:-}" ]]; then return 0; fi
readonly ARCH_INSTALLER_HOOKS_LOADED="true"

run_hook_directory() {
    local directory="$1"
    local hook
    [[ -d "${directory}" ]] || return 0
    while IFS= read -r hook; do
        [[ -x "${hook}" ]] || continue
        run_command "${hook}" || return 1
    done < <(find "${directory}" -maxdepth 1 -type f -print | LC_ALL=C sort)
}
