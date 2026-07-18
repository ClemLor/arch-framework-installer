#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
readonly ROOT
source "${ROOT}/lib/state.sh"

STATE_FIXTURE="$(mktemp -d)"
readonly STATE_FIXTURE
trap 'rm -r "${STATE_FIXTURE}"' EXIT

DRY_RUN=true
STATE_FILE=""
state_init "${STATE_FIXTURE}"
state_reset
[[ -z "${STATE_FILE}" ]]
[[ ! -e "${STATE_FIXTURE}/state/install.state" ]]
printf '%s\n' 'ok - dry-run does not depend on a persistent state file'

DRY_RUN=false
state_init "${STATE_FIXTURE}"
state_reset
[[ "${STATE_FILE}" == "${STATE_FIXTURE}/state/install.state" ]]
[[ -s "${STATE_FILE}" ]]
grep -Fq 'started_at=' "${STATE_FILE}"
printf '%s\n' 'ok - real workflows retain persistent diagnostic state'
