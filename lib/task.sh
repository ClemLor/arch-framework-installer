#!/usr/bin/env bash

if [[ -n "${ARCH_INSTALLER_TASK_LOADED:-}" ]]; then
    return 0
fi
readonly ARCH_INSTALLER_TASK_LOADED="true"

# See the note in lib/logging.sh: events are optional, stubbed only if absent.
if ! declare -F event_emit >/dev/null; then
    event_plan() { :; }
    event_plan_task() { :; }
    event_task_begin() { :; }
    event_phase() { :; }
    event_task_end() { :; }
    event_task_failed() { :; }
    event_rollback_begin() { :; }
    event_rollback_end() { :; }
fi

declare -ag TASK_IDS=()
declare -Ag TASK_FILES=()

task_function() {
    printf 'task_%s_%s' "$1" "$2"
}

task_register_file() {
    local file="$1"
    local filename
    local id
    local phase
    local function_name

    filename="${file##*/}"
    id="${filename%.sh}"
    id="${id#[0-9][0-9]_}"

    # shellcheck source=/dev/null
    source "${file}" || return 1

    for phase in name validate execute verify cleanup rollback; do
        function_name="$(task_function "${id}" "${phase}")"
        if ! declare -F "${function_name}" >/dev/null; then
            error "Task ${file} is missing ${function_name}."
            return 1
        fi
    done

    if [[ -n "${TASK_FILES[${id}]:-}" ]]; then
        error "Duplicate task id: ${id}."
        return 1
    fi

    TASK_IDS+=("${id}")
    TASK_FILES["${id}"]="${file}"
}

task_discover() {
    local directory="$1"
    local file

    TASK_IDS=()
    TASK_FILES=()

    while IFS= read -r file; do
        [[ -s "${file}" ]] || continue
        task_register_file "${file}" || return 1
    done < <(find "${directory}" -maxdepth 1 -type f -name '[0-9][0-9]_*.sh' -print | LC_ALL=C sort)

    if (( ${#TASK_IDS[@]} == 0 )); then
        error "No task found in ${directory}."
        return 1
    fi
}

task_run_cleanup() {
    local id="$1"
    local cleanup_function
    cleanup_function="$(task_function "${id}" cleanup)"
    TASK_PHASE="cleanup"
    state_persist
    "${cleanup_function}"
}

# The plan, announced once discovery has read it.
#
# Emitted here rather than inside task_discover so discovery stays a pure listing
# operation, which is what its test checks.
task_emit_plan() {
    local total="$1"
    local index=0
    local id

    event_plan "${total}"
    for id in "${TASK_IDS[@]}"; do
        ((index += 1))
        event_plan_task "${index}" "${id}" "$("$(task_function "${id}" name)")"
    done
}

task_rollback_completed() {
    local index
    local id
    local rollback_function
    local status
    local failed="false"

    if [[ "${DRY_RUN:-false}" == "true" ]]; then
        info "Dry-run created no resources; rollback is not required."
        return 0
    fi

    for ((index=${#TASK_COMPLETED[@]} - 1; index >= 0; index--)); do
        id="${TASK_COMPLETED[index]}"
        rollback_function="$(task_function "${id}" rollback)"
        TASK_PHASE="rollback"
        state_persist
        warn "Rolling back task: ${id}"
        TASK_ROLLBACK_HAPPENED="true"
        event_rollback_begin "${id}" completed
        status=0
        if ! "${rollback_function}"; then
            status=1
            error "Rollback failed for task: ${id}"
            failed="true"
        fi
        event_rollback_end "${id}" completed "${status}"
    done

    [[ "${failed}" == "false" ]]
}

task_run_one() {
    local id="$1"
    local current="$2"
    local total="$3"
    local name_function
    local name
    local phase
    local function_name
    local started_at
    local duration
    local status=0
    local execute_started="false"
    # Captured when it fails, because `phase` is reassigned below when cleanup
    # also fails, and "execute failed" is the fact worth reporting.
    local failed_phase=""

    name_function="$(task_function "${id}" name)"
    name="$("${name_function}")"
    TASK_CURRENT="${id}"
    state_persist
    started_at="$(date +%s)"
    progress_start "${current}" "${total}" "${name}"
    event_task_begin "${current}" "${total}" "${id}" "${name}"

    if declare -F run_hook_directory >/dev/null; then
        run_hook_directory "$(project_root)/hooks/pre-task" || return 1
    fi

    for phase in validate execute verify; do
        if [[ "${TASK_INTERRUPTED}" == "true" ]]; then
            status=130
            break
        fi
        TASK_PHASE="${phase}"
        state_persist
        event_phase "${current}" "${id}" "${phase}"
        [[ "${phase}" == "execute" ]] && execute_started="true"
        function_name="$(task_function "${id}" "${phase}")"
        log_message "TASK" "${id}: ${phase} started"
        # `if "${f}"; then :; else status=$?; fi` rather than `if ! "${f}"`: after
        # a negation, $? is the negation's own result, so every failure used to be
        # reported as 1 and the phase's real exit code was lost.
        if "${function_name}"; then
            :
        else
            status=$?
            [[ "${status}" -ne 0 ]] || status=1
            failed_phase="${phase}"
            log_message "TASK" "${id}: ${phase} failed status=${status}"
            break
        fi
    done

    event_phase "${current}" "${id}" cleanup
    if ! task_run_cleanup "${id}"; then
        [[ "${status}" -ne 0 ]] || status=1
        phase="cleanup"
        [[ -n "${failed_phase}" ]] || failed_phase="cleanup"
    fi

    if [[ "${status}" -ne 0 ]]; then
        # An interrupt breaks the loop without any phase having failed, so the
        # phase it was noticed in is the honest answer.
        [[ -n "${failed_phase}" ]] || failed_phase="${phase}"
        if [[ "${execute_started}" == "true" ]] && [[ "${DRY_RUN:-false}" != "true" ]]; then
            function_name="$(task_function "${id}" rollback)"
            warn "Rolling back partially executed task: ${id}"
            TASK_ROLLBACK_HAPPENED="true"
            event_rollback_begin "${id}" partial
            if "${function_name}"; then
                event_rollback_end "${id}" partial 0
            else
                error "Rollback failed for partially executed task: ${id}"
                event_rollback_end "${id}" partial 1
            fi
        fi
        progress_failure "${current}" "${total}" "${name}" "${phase}"
        event_task_failed "${current}" "${id}" "${failed_phase}" "${status}"
        return "${status}"
    fi

    if declare -F run_hook_directory >/dev/null; then
        if ! run_hook_directory "$(project_root)/hooks/post-task"; then
            function_name="$(task_function "${id}" rollback)"
            "${function_name}" || error "Rollback failed after post-task hook failure: ${id}"
            return 1
        fi
    fi

    state_mark_completed "${id}"
    duration="$(( $(date +%s) - started_at ))"
    progress_success "${current}" "${total}" "${name}" "${duration}"
    event_task_end "${current}" "${id}" "${duration}"
}

task_run_all() {
    local tasks_directory="$1"
    local current=0
    local total
    local id
    local status=0

    state_reset
    task_discover "${tasks_directory}" || return 1
    total="${#TASK_IDS[@]}"
    task_emit_plan "${total}"
    trap 'state_request_interrupt INT' INT
    trap 'state_request_interrupt TERM' TERM

    if declare -F run_hook_directory >/dev/null; then
        if ! run_hook_directory "$(project_root)/hooks/pre-install"; then
            trap - INT TERM
            return 1
        fi
    fi

    for id in "${TASK_IDS[@]}"; do
        ((current += 1))
        if ! task_run_one "${id}" "${current}" "${total}"; then
            status=$?
            [[ "${status}" -ne 0 ]] || status=1
            task_rollback_completed || true
            break
        fi
        if [[ -n "${TASK_STOP_AFTER:-}" ]] && [[ "${id}" == "${TASK_STOP_AFTER}" ]]; then
            TASK_STOPPED_AFTER="${id}"
            break
        fi
    done

    trap - INT TERM
    state_clear_current

    if [[ "${TASK_INTERRUPTED}" == "true" ]]; then
        return 130
    fi
    if [[ "${status}" -eq 0 ]] && declare -F run_hook_directory >/dev/null; then
        if ! run_hook_directory "$(project_root)/hooks/post-install"; then
            task_rollback_completed || true
            return 1
        fi
    fi
    return "${status}"
}
