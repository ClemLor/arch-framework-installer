#!/usr/bin/env bash
# Ten thousand log lines on both streams, to prove the reader neither deadlocks
# on a full pipe nor grows without bound.
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

emit run_begin "protocol=1" "dry_run=true"
emit plan "total=1"
emit plan_task "index=1" "id=alpha" "name=First task"
emit task_begin "index=1" "total=1" "id=alpha" "name=First task"

for ((index = 0; index < 10000; index++)); do
    emit log "level=INFO" "message=event line ${index}"
    printf 'stdout line %d\n' "${index}"
done

emit task_end "index=1" "id=alpha" "status=0" "duration=3"
emit run_end "status=0" "interrupted=false" "rolled_back=false" "stopped_after=" "completed=alpha"
