#!/usr/bin/env bash
#
# The mock task phases are called by name by the engine, and MOCK_NAME is read
# inside a function body built with eval, so neither looks used from here.
# shellcheck disable=SC2034,SC2329
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
readonly ROOT
source "${ROOT}/lib/logging.sh"
source "${ROOT}/lib/state.sh"
source "${ROOT}/lib/progress.sh"
source "${ROOT}/lib/task.sh"
source "${ROOT}/lib/events.sh"

TESTS=0
FAILURES=0
WORK="$(mktemp -d)"
trap 'rm -rf "${WORK}"' EXIT

assert_equal() {
    local expected="$1" actual="$2" message="$3"
    ((TESTS += 1))
    if [[ "${expected}" != "${actual}" ]]; then
        printf 'not ok - %s (expected=%q actual=%q)\n' "${message}" "${expected}" "${actual}" >&2
        ((FAILURES += 1))
    else
        printf 'ok - %s\n' "${message}"
    fi
}

assert_contains() {
    local haystack="$1" needle="$2" message="$3"
    ((TESTS += 1))
    if [[ "${haystack}" != *"${needle}"* ]]; then
        printf 'not ok - %s (missing=%q in=%q)\n' "${message}" "${needle}" "${haystack}" >&2
        ((FAILURES += 1))
    else
        printf 'ok - %s\n' "${message}"
    fi
}

define_task() {
    local id="$1"
    local name="${2:-Mock}"
    eval "task_${id}_name() { printf '%s' \"\${MOCK_NAME:-${name}}\"; }"
    eval "task_${id}_validate() { :; }"
    eval "task_${id}_execute() { :; }"
    eval "task_${id}_verify() { :; }"
    eval "task_${id}_cleanup() { :; }"
    eval "task_${id}_rollback() { :; }"
}

# One task run, with the human output captured and the events sent wherever the
# caller says. Returns the task's own status.
run_task() {
    local capture="$1"
    local event_file="${2:-}"
    local status=0

    TASK_COMPLETED=()
    TASK_INTERRUPTED=false
    STATE_FILE=""
    EVENTS_ENABLED="false"
    unset AFI_EVENT_FD

    if [[ -n "${event_file}" ]]; then
        exec {event_fd}>"${event_file}"
        AFI_EVENT_FD="${event_fd}"
        export AFI_EVENT_FD
        event_init
    fi

    task_run_one mock 1 3 >"${capture}" 2>&1 || status=$?

    if [[ -n "${event_file}" ]]; then
        exec {event_fd}>&-
        unset AFI_EVENT_FD
        EVENTS_ENABLED="false"
    fi
    return "${status}"
}

# The kinds in order, without the log records: those mirror every message the
# installer writes and would make each assertion a transcript of the log.
kinds_in() {
    awk -F'\t' '$2 != "log" { printf "%s ", $2 }' "$1"
}

records_in() {
    awk -F'\t' '$2 != "log"' "$1" | wc -l | tr -d ' '
}

field_of() {
    local file="$1" kind="$2" key="$3"
    awk -F'\t' -v kind="${kind}" -v key="${key}" '
        $2 == kind {
            for (i = 3; i <= NF; i++) {
                split($i, pair, "=")
                if (pair[1] == key) {
                    value = substr($i, length(pair[1]) + 2)
                    printf "%s", value
                    exit
                }
            }
        }' "${file}"
}

# The requirement is that a run with a front-end attached prints exactly what a
# run without one prints. A diff of both captures is the only check that actually
# tests that; an assertion on a line or two would not have noticed a stray
# newline.
test_human_output_is_unchanged() {
    define_task mock 'GPT partitioning'
    run_task "${WORK}/quiet.out"
    run_task "${WORK}/watched.out" "${WORK}/watched.events"

    if diff -u "${WORK}/quiet.out" "${WORK}/watched.out" >"${WORK}/diff" 2>&1; then
        assert_equal identical identical 'human output is byte-identical with events on'
    else
        printf 'not ok - human output changed when events were enabled\n' >&2
        cat "${WORK}/diff" >&2
        ((TESTS += 1))
        ((FAILURES += 1))
    fi
}

test_record_shape() {
    define_task mock 'GPT partitioning'
    run_task "${WORK}/shape.out" "${WORK}/shape.events"

    assert_equal "AFI1" "$(awk -F'\t' 'NR == 1 { printf "%s", $1 }' "${WORK}/shape.events")" \
        'every record starts with the protocol tag'
    assert_equal 'task_begin phase phase phase phase task_end ' \
        "$(kinds_in "${WORK}/shape.events")" \
        'a successful task reports its four phases between begin and end'
    assert_equal 'GPT partitioning' "$(field_of "${WORK}/shape.events" task_begin name)" \
        'a name containing spaces survives without quoting'
    assert_equal 'validate' "$(field_of "${WORK}/shape.events" phase phase)" \
        'the first phase reported is validate'
}

test_values_are_scrubbed() {
    define_task mock
    MOCK_NAME="$(printf 'tabbed\tname\nsecond line')"
    run_task "${WORK}/scrub.out" "${WORK}/scrub.events"
    unset MOCK_NAME

    assert_equal 'tabbed name second line' \
        "$(field_of "${WORK}/scrub.events" task_begin name)" \
        'tabs and newlines in a value become spaces'
    assert_equal 6 "$(records_in "${WORK}/scrub.events")" \
        'a value with a newline still produces one record per event'
}

test_failure_reports_the_phase_that_failed() {
    define_task mock
    task_mock_execute() { return 7; }
    run_task "${WORK}/fail.out" "${WORK}/fail.events" || true
    task_mock_execute() { :; }

    assert_equal 'execute' "$(field_of "${WORK}/fail.events" task_failed phase)" \
        'the failing phase is named'
    assert_equal '7' "$(field_of "${WORK}/fail.events" task_failed status)" \
        'the exit code of the failing phase is carried through, not flattened to 1'
}

# Execute fails, then cleanup fails too. The printed line says "cleanup" because
# the variable it reads is reassigned; the event must still say what actually
# broke.
test_a_failing_cleanup_does_not_mask_the_real_failure() {
    define_task mock
    task_mock_execute() { return 7; }
    task_mock_cleanup() { return 1; }
    run_task "${WORK}/mask.out" "${WORK}/mask.events" || true
    task_mock_execute() { :; }
    task_mock_cleanup() { :; }

    assert_equal 'execute' "$(field_of "${WORK}/mask.events" task_failed phase)" \
        'a failing cleanup does not overwrite the reported failure'
}

test_rollback_is_reported() {
    define_task mock
    task_mock_execute() { return 7; }
    DRY_RUN="false"
    run_task "${WORK}/rollback.out" "${WORK}/rollback.events" || true
    task_mock_execute() { :; }
    unset DRY_RUN

    assert_contains "$(kinds_in "${WORK}/rollback.events")" 'rollback_begin rollback_end' \
        'a partially executed task reports its rollback'
    assert_equal 'partial' "$(field_of "${WORK}/rollback.events" rollback_begin scope)" \
        'the rollback scope distinguishes one task from the whole run'
}

test_the_plan_is_announced_before_the_first_task() {
    local fixture id prefix
    fixture="$(mktemp -d)"
    for id in later earlier; do
        prefix=20
        [[ "${id}" == earlier ]] && prefix=10
        {
            printf 'task_%s_name() { printf "Task %s"; }\n' "${id}" "${id}"
            printf 'task_%s_validate() { :; }\n' "${id}"
            printf 'task_%s_execute() { :; }\n' "${id}"
            printf 'task_%s_verify() { :; }\n' "${id}"
            printf 'task_%s_cleanup() { :; }\n' "${id}"
            printf 'task_%s_rollback() { :; }\n' "${id}"
        } >"${fixture}/${prefix}_${id}.sh"
    done

    exec {plan_fd}>"${WORK}/plan.events"
    AFI_EVENT_FD="${plan_fd}"
    export AFI_EVENT_FD
    event_init
    task_discover "${fixture}"
    task_emit_plan "${#TASK_IDS[@]}"
    exec {plan_fd}>&-
    unset AFI_EVENT_FD
    EVENTS_ENABLED="false"
    rm -r "${fixture}"

    assert_equal 'plan plan_task plan_task ' "$(kinds_in "${WORK}/plan.events")" \
        'the plan is announced once, with one record per task'
    assert_equal '2' "$(field_of "${WORK}/plan.events" plan total)" 'the total is reported'
    assert_equal 'Task earlier' "$(field_of "${WORK}/plan.events" plan_task name)" \
        'the plan is in execution order'
}

test_a_reader_that_went_away_does_not_stop_the_install() {
    local status=0
    define_task mock

    # A pipe whose reader has already exited: writing raises SIGPIPE, which by
    # default kills a non-interactive shell — mid-installation, on a half-written
    # disk.
    exec {dead_fd}> >(exec true)
    sleep 0.2
    AFI_EVENT_FD="${dead_fd}"
    export AFI_EVENT_FD
    event_init

    local index
    for ((index = 0; index < 200; index++)); do
        event_log INFO "message ${index}" || status=1
    done

    exec {dead_fd}>&- 2>/dev/null || true
    unset AFI_EVENT_FD

    assert_equal 0 "${status}" 'emitting to a dead reader keeps returning success'
    assert_equal 'false' "${EVENTS_ENABLED}" 'a dead reader turns emission off'
    EVENTS_ENABLED="false"
}

test_an_unusable_descriptor_disables_events_cleanly() {
    # Closed explicitly rather than assumed closed: the descriptor was open in at
    # least one environment this ran in, and the test then proved nothing.
    exec 9>&- || true
    AFI_EVENT_FD="9"
    export AFI_EVENT_FD
    event_init 2>/dev/null
    assert_equal 'false' "${EVENTS_ENABLED}" 'a closed descriptor disables emission'

    AFI_EVENT_FD="not-a-number"
    event_init 2>/dev/null
    assert_equal 'false' "${EVENTS_ENABLED}" 'a descriptor that is not a number disables emission'
    unset AFI_EVENT_FD
}

test_events_are_off_by_default() {
    unset AFI_EVENT_FD
    event_init
    assert_equal 'false' "${EVENTS_ENABLED}" 'no descriptor means no events'
    event_log INFO 'this goes nowhere'
}

test_events_are_off_by_default
test_human_output_is_unchanged
test_record_shape
test_values_are_scrubbed
test_failure_reports_the_phase_that_failed
test_a_failing_cleanup_does_not_mask_the_real_failure
test_rollback_is_reported
test_the_plan_is_announced_before_the_first_task
test_a_reader_that_went_away_does_not_stop_the_install
test_an_unusable_descriptor_disables_events_cleanly

printf '%d tests, %d failures\n' "${TESTS}" "${FAILURES}"
((FAILURES == 0))
