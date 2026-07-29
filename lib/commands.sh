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
    if [[ "$#" -eq 0 ]]; then
        error "run_command requires at least one argument."
        return 1
    fi

    # Markers go to stderr so that callers using $(run_command ...) never
    # capture them as data.
    if [[ "${DRY_RUN}" == "true" ]]; then
        {
            printf '[DRY-RUN] '
            format_command "$@"
            printf '\n'
        } >&2
        return 0
    fi

    if [[ "${VERBOSE}" == "true" ]]; then
        {
            printf '[COMMAND] '
            format_command "$@"
            printf '\n'
        } >&2
    fi

    "$@"
}

run_critical() {
    local description="$1"
    shift

    info "${description}"

    if ! run_command "$@"; then
        fatal "Failed: ${description}"
    fi
}

# Read-only commands only.
#
# Nothing enforces that invariant, so it matters: capture_command always
# executes, including in dry-run mode, because its output is consumed as data
# by the caller. A dry-run placeholder would be captured instead of the real
# value and silently corrupt every decision made from it.
capture_command() {
    if [[ "$#" -eq 0 ]]; then
        error "capture_command requires at least one argument."
        return 1
    fi

    if [[ "${VERBOSE}" == "true" ]]; then
        {
            printf '[CAPTURE] '
            format_command "$@"
            printf '\n'
        } >&2
    fi

    "$@"
}
