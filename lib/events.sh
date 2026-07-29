#!/usr/bin/env bash

# ==============================================================================
# Module: events
#
# Purpose:
#   Emit a machine-readable copy of what the installer is doing, for a front-end
#   that draws it. The human output on stdout and stderr is untouched: when
#   AFI_EVENT_FD is unset — which is every ordinary run — every function here
#   returns immediately and writes nothing.
#
# Transport:
#   An already-open file descriptor, named by number in AFI_EVENT_FD. A pipe
#   gives the reader a real end-of-file when the installer and all its children
#   are done, which a plain file cannot, and it leaves nothing behind on the
#   filesystem to clean up. The parent opens it; this module only writes.
#
# Format:
#   AFI1<TAB>kind<TAB>key=value<TAB>...
#   Values have tabs, newlines and carriage returns replaced by spaces, so a
#   record is always exactly one line and a value containing spaces needs no
#   quoting. Parse by splitting on tabs, then on the first '=' of each field.
#
# Idempotent:
#   Yes
# ==============================================================================

if [[ -n "${ARCH_INSTALLER_EVENTS_LOADED:-}" ]]; then
    return 0
fi
readonly ARCH_INSTALLER_EVENTS_LOADED="true"

readonly EVENT_PROTOCOL="AFI1"

EVENTS_ENABLED="false"
EVENT_RUN_ENDED="false"

event_enabled() {
    [[ "${EVENTS_ENABLED}" == "true" ]]
}

# Turn emission on if the descriptor is there and writable.
#
# A descriptor that was never passed, or was closed, disables events rather than
# failing: a front-end is an optional observer, and an installation must not
# depend on being watched.
event_init() {
    EVENTS_ENABLED="false"

    [[ -n "${AFI_EVENT_FD:-}" ]] || return 0
    [[ "${AFI_EVENT_FD}" =~ ^[0-9]+$ ]] || {
        warn "AFI_EVENT_FD is not a descriptor number; progress events are off."
        return 0
    }

    if ! { true >&"${AFI_EVENT_FD}"; } 2>/dev/null; then
        warn "AFI_EVENT_FD=${AFI_EVENT_FD} is not writable; progress events are off."
        return 0
    fi

    # A handler, not 'trap "" PIPE'. SIG_IGN would be inherited by every child,
    # and several helpers here are `producer | grep -q` pipelines whose producers
    # rely on SIGPIPE to stop early. A reader that goes away must cost us the
    # events, not the installation.
    trap 'EVENTS_ENABLED="false"' PIPE

    EVENTS_ENABLED="true"
    return 0
}

# Write one record. Never fails the caller: install.sh runs under `set -Eeuo
# pipefail`, and telemetry that can abort an install is worse than no telemetry.
event_emit() {
    local kind="$1"
    local field
    local line

    event_enabled || return 0
    shift

    line="${EVENT_PROTOCOL}"$'\t'"${kind}"
    for field in "$@"; do
        # Inline expansion rather than a helper: log_message emits an event for
        # every command the installer runs, and a command substitution per field
        # would add thousands of forks to an installation.
        field="${field//$'\t'/ }"
        field="${field//$'\n'/ }"
        field="${field//$'\r'/ }"
        line+=$'\t'"${field}"
    done

    # Grouped so the descriptor and the error redirection do not read as two
    # competing redirections of stderr.
    { printf '%s\n' "${line}" >&"${AFI_EVENT_FD}"; } 2>/dev/null ||
        EVENTS_ENABLED="false"
    return 0
}

event_run_begin() {
    local tasks_directory="$1"

    event_emit run_begin \
        "protocol=1" \
        "pid=$$" \
        "dry_run=${DRY_RUN:-false}" \
        "log_file=${LOG_FILE:-}" \
        "state_file=${STATE_FILE:-}" \
        "tasks_dir=${tasks_directory}"
}

# The whole plan, before the first task starts, so a front-end can show every
# step as pending instead of growing a list one line at a time.
event_plan() {
    event_emit plan "total=$1"
}

event_plan_task() {
    event_emit plan_task "index=$1" "id=$2" "name=$3"
}

event_task_begin() {
    event_emit task_begin "index=$1" "total=$2" "id=$3" "name=$4"
}

event_phase() {
    event_emit phase "index=$1" "id=$2" "phase=$3"
}

event_task_end() {
    event_emit task_end "index=$1" "id=$2" "status=0" "duration=$3"
}

event_task_failed() {
    event_emit task_failed "index=$1" "id=$2" "phase=$3" "status=$4"
}

event_rollback_begin() {
    event_emit rollback_begin "id=$1" "scope=$2"
}

event_rollback_end() {
    event_emit rollback_end "id=$1" "scope=$2" "status=$3"
}

event_interrupt() {
    event_emit interrupt "signal=$1"
}

event_log() {
    event_emit log "level=$1" "message=$2"
}

event_run_end() {
    event_emit run_end \
        "status=$1" \
        "interrupted=${TASK_INTERRUPTED:-false}" \
        "rolled_back=${TASK_ROLLBACK_HAPPENED:-false}" \
        "stopped_after=${TASK_STOPPED_AFTER:-}" \
        "completed=${TASK_COMPLETED[*]:-}"
}

# Called both from main and from an EXIT trap: a `fatal` in configuration
# loading exits before any task runs, and a reader left waiting for a run_end
# that never comes cannot tell that from an installation still working.
event_run_end_once() {
    [[ "${EVENT_RUN_ENDED}" == "true" ]] && return 0
    EVENT_RUN_ENDED="true"
    event_run_end "$1"
}
