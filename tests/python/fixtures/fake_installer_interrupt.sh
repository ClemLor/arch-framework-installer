#!/usr/bin/env bash
# Waits to be interrupted, then behaves as lib/task.sh does: reports the signal,
# rolls back and exits 130.
set -Eeuo pipefail

TAB=$'\t'

emit() {
    local kind="$1"
    shift
    local line="AFI1${TAB}${kind}"
    local field
    for field in "$@"; do
        line+="${TAB}${field}"
    done
    printf '%s\n' "${line}" >&"${AFI_EVENT_FD}"
}

on_interrupt() {
    emit interrupt "signal=INT"
    emit rollback_begin "id=alpha" "scope=completed"
    emit rollback_end "id=alpha" "scope=completed" "status=0"
    emit run_end "status=130" "interrupted=true" "rolled_back=true" "stopped_after=" "completed="
    exit 130
}

trap on_interrupt INT

emit run_begin "protocol=1" "dry_run=true"
emit plan "total=1"
emit plan_task "index=1" "id=alpha" "name=First task"
emit task_begin "index=1" "total=1" "id=alpha" "name=First task"
emit phase "index=1" "id=alpha" "phase=execute"
printf 'ready\n'

# `wait` rather than a plain sleep, so the trap runs immediately instead of after
# the current command finishes.
sleep 30 &
wait $! || true
