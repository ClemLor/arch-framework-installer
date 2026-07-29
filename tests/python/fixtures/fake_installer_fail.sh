#!/usr/bin/env bash
# A run that fails in execute and rolls the task back.
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
emit plan "total=2"
emit plan_task "index=1" "id=alpha" "name=First task"
emit plan_task "index=2" "id=beta" "name=Second task"

emit task_begin "index=1" "total=2" "id=alpha" "name=First task"
emit phase "index=1" "id=alpha" "phase=validate"
emit phase "index=1" "id=alpha" "phase=execute"
printf 'something went wrong\n' >&2
emit rollback_begin "id=alpha" "scope=partial"
emit rollback_end "id=alpha" "scope=partial" "status=0"
emit task_failed "index=1" "id=alpha" "phase=execute" "status=7"
emit run_end "status=7" "interrupted=false" "rolled_back=true" "stopped_after=" "completed="

exit 7
