#!/usr/bin/env bash
set -Eeuo pipefail

readonly ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
source "${ROOT}/lib/logging.sh"
source "${ROOT}/lib/state.sh"
source "${ROOT}/lib/progress.sh"
source "${ROOT}/lib/task.sh"

TESTS=0
FAILURES=0
EVENTS=""

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

record() { EVENTS+="$1 "; }

test_success_order() {
    task_alpha_name() { printf Alpha; }
    task_alpha_validate() { record alpha_validate; }
    task_alpha_execute() { record alpha_execute; }
    task_alpha_verify() { record alpha_verify; }
    task_alpha_cleanup() { record alpha_cleanup; }
    task_alpha_rollback() { record alpha_rollback; }
    TASK_IDS=(alpha)
    TASK_COMPLETED=()
    TASK_INTERRUPTED=false
    EVENTS=""
    task_run_one alpha 1 1 >/dev/null
    assert_equal 'alpha_validate alpha_execute alpha_verify alpha_cleanup ' "${EVENTS}" 'validate, execute, verify and cleanup order'
    assert_equal 'alpha' "${TASK_COMPLETED[*]}" 'successful task is recorded'
}

test_failure_rollback() {
    task_beta_name() { printf Beta; }
    task_beta_validate() { record beta_validate; }
    task_beta_execute() { record beta_execute; return 7; }
    task_beta_verify() { record beta_verify; }
    task_beta_cleanup() { record beta_cleanup; }
    task_beta_rollback() { record beta_rollback; }
    TASK_COMPLETED=()
    TASK_INTERRUPTED=false
    EVENTS=""
    if task_run_one beta 1 1 >/dev/null 2>&1; then
        assert_equal failure success 'failed execution returns non-zero'
    else
        assert_equal failure failure 'failed execution returns non-zero'
    fi
    assert_equal 'beta_validate beta_execute beta_cleanup beta_rollback ' "${EVENTS}" 'partial task cleanup and rollback order'
}

test_discovery_order() {
    local fixture
    local id
    fixture="$(mktemp -d)"
    for id in later earlier; do
        local prefix=20
        [[ "${id}" == earlier ]] && prefix=10
        printf 'task_%s_name() { printf %s; }\ntask_%s_validate() { :; }\ntask_%s_execute() { :; }\ntask_%s_verify() { :; }\ntask_%s_cleanup() { :; }\ntask_%s_rollback() { :; }\n' \
            "${id}" "${id}" "${id}" "${id}" "${id}" "${id}" "${id}" >"${fixture}/${prefix}_${id}.sh"
    done
    task_discover "${fixture}"
    assert_equal 'earlier later' "${TASK_IDS[*]}" 'task discovery is ordered by filename'
    rm -r "${fixture}"
}

test_reverse_rollback() {
    task_gamma_rollback() { record gamma; }
    task_delta_rollback() { record delta; }
    TASK_COMPLETED=(gamma delta)
    EVENTS=""
    task_rollback_completed >/dev/null 2>&1
    assert_equal 'delta gamma ' "${EVENTS}" 'completed tasks roll back in reverse order'
}

test_success_order
test_failure_rollback
test_discovery_order
test_reverse_rollback

printf '%d tests, %d failures\n' "${TESTS}" "${FAILURES}"
((FAILURES == 0))
