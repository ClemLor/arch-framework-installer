#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
readonly ROOT
source "${ROOT}/lib/logging.sh"
source "${ROOT}/lib/common.sh"
source "${ROOT}/lib/commands.sh"

COMMAND_LOG="$(mktemp)"
readonly COMMAND_LOG
trap 'rm -f "${COMMAND_LOG}"' EXIT

CALLED=false
dangerous_mock() { CALLED=true; }

DRY_RUN=true
run_command dangerous_mock >/dev/null
if [[ "${CALLED}" == "false" ]]; then
    printf '%s\n' 'ok - dry-run does not execute the command'
else
    printf '%s\n' 'not ok - dry-run executed the command' >&2
    exit 1
fi

command_exists() { return 1; }
DRY_RUN=true
require_commands_for_mode Test missing-command >/dev/null
printf '%s\n' 'ok - missing prospective commands only warn in dry-run'

DRY_RUN=false
if require_commands_for_mode Test missing-command >/dev/null 2>&1; then
    printf '%s\n' 'not ok - real mode accepted a missing command' >&2
    exit 1
fi
printf '%s\n' 'ok - missing commands remain fatal in real mode'

LOG_FILE="${COMMAND_LOG}"
VERBOSE=true
CAPTURED="$(capture_logged_command printf 'machine-output' 2>/dev/null)"
[[ "${CAPTURED}" == "machine-output" ]]
grep -Fq '[COMMAND] start:' "${COMMAND_LOG}"
grep -Fq '[COMMAND] finish: status=0' "${COMMAND_LOG}"
printf '%s\n' 'ok - captured command output remains clean and execution is logged'
