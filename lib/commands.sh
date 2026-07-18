#!/usr/bin/env bash

# ==============================================================================
# Module: commands
#
# Purpose:
#   Execute commands consistently with logging, error handling and dry-run
#   support.
#
# Idempotent:
#   Yes
# ==============================================================================

if [[ -n "${ARCH_INSTALLER_COMMANDS_LOADED:-}" ]]; then
    return 0
fi

readonly ARCH_INSTALLER_COMMANDS_LOADED="true"

DRY_RUN="${DRY_RUN:-false}"
VERBOSE="${VERBOSE:-false}"

format_command() {
    printf '%q ' "$@"
}

run_command() {
    local started_at
    local finished_at
    local status
    local rendered_command

    if [[ "$#" -eq 0 ]]; then
        error "run_command requires at least one argument."
        return 1
    fi

    printf -v rendered_command '%q ' "$@"

    if [[ "${DRY_RUN}" == "true" ]]; then
        log_message "DRY-RUN" "${rendered_command}"
        printf '[DRY-RUN] '
        format_command "$@"
        printf '\n'
        return 0
    fi

    if [[ "${VERBOSE}" == "true" ]]; then
        printf '[COMMAND] '
        format_command "$@"
        printf '\n'
    fi

    started_at="$(date +%s)"
    log_message "COMMAND" "start: ${rendered_command}"

    if "$@"; then
        status=0
    else
        status=$?
    fi

    finished_at="$(date +%s)"
    log_message "COMMAND" "finish: status=${status} duration=$((finished_at - started_at))s command=${rendered_command}"
    return "${status}"
}

run_critical() {
    local description="$1"
    shift

    info "${description}"

    if ! run_command "$@"; then
        error "Failed: ${description}"
        return 1
    fi
}

capture_command() {
    if [[ "$#" -eq 0 ]]; then
        error "capture_command requires at least one argument."
        return 1
    fi

    if [[ "${DRY_RUN}" == "true" ]]; then
        printf '[DRY-RUN] '
        format_command "$@"
        printf '\n'
        return 0
    fi

    "$@"
}
