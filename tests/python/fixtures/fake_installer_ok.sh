#!/usr/bin/env bash
# A successful two-task run, emitted the way lib/events.sh does.
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

emit run_begin "protocol=1" "dry_run=true" "log_file=logs/fake.log"
emit plan "total=2"
emit plan_task "index=1" "id=alpha" "name=First task"
emit plan_task "index=2" "id=beta" "name=Second task"

for pair in "1 alpha" "2 beta"; do
    set -- ${pair}
    printf '[%02d/02] task %s …\n' "$1" "$2"
    emit task_begin "index=$1" "total=2" "id=$2" "name=Task $2"
    for phase in validate execute verify cleanup; do
        emit phase "index=$1" "id=$2" "phase=${phase}"
    done
    # A tick on stdout, to prove the reader survives a multi-byte character
    # arriving in pieces.
    printf '[%02d/02] task %s ✔ (1s)\n' "$1" "$2"
    emit task_end "index=$1" "id=$2" "status=0" "duration=1"
done

emit run_end "status=0" "interrupted=false" "rolled_back=false" "stopped_after=" "completed=alpha beta"
