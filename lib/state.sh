#!/usr/bin/env bash

if [[ -n "${ARCH_INSTALLER_STATE_LOADED:-}" ]]; then
    return 0
fi
readonly ARCH_INSTALLER_STATE_LOADED="true"

declare -ag TASK_COMPLETED=()
TASK_CURRENT=""
TASK_PHASE=""
TASK_INTERRUPTED="false"
TASK_SIGNAL=""
INSTALL_STARTED_AT=0
STATE_FILE="${STATE_FILE:-}"

state_init() {
    local root="$1"
    mkdir -p "${root}/state" || return 1
    STATE_FILE="${STATE_FILE:-${root}/state/install.state}"
}

state_persist() {
    local completed
    [[ -n "${STATE_FILE}" ]] || return 0
    completed="${TASK_COMPLETED[*]:-}"
    {
        printf 'started_at=%q\n' "${INSTALL_STARTED_AT}"
        printf 'current=%q\n' "${TASK_CURRENT}"
        printf 'phase=%q\n' "${TASK_PHASE}"
        printf 'completed=%q\n' "${completed}"
        printf 'interrupted=%q\n' "${TASK_INTERRUPTED}"
        printf 'signal=%q\n' "${TASK_SIGNAL}"
    } >"${STATE_FILE}"
}

state_reset() {
    TASK_COMPLETED=()
    TASK_CURRENT=""
    TASK_PHASE=""
    TASK_INTERRUPTED="false"
    TASK_SIGNAL=""
    INSTALL_STARTED_AT="$(date +%s)"
    state_persist
}

state_mark_completed() {
    TASK_COMPLETED+=("$1")
    state_persist
}

state_request_interrupt() {
    TASK_INTERRUPTED="true"
    TASK_SIGNAL="$1"
    state_persist
    warn "Signal ${TASK_SIGNAL} received; cleanup and rollback will run."
}
