#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
readonly ROOT
source "${ROOT}/lib/logging.sh"
source "${ROOT}/lib/luks.sh"
source "${ROOT}/tasks/20_encryption.sh"

DRY_RUN=false
LUKS_NAME=cryptroot
TPM2_ENABLED=false
CALLS=""
get_system_partition_path() { printf /dev/mock2; }
run_command() { CALLS+="$* "; }
validate_luks_dependencies() { return 0; }
confirm_destructive_action() { CALLS+="confirm "; }

LUKS_ENABLED=false
[[ "$(root_block_device)" == /dev/mock2 ]]
task_encryption_validate
task_encryption_execute >/dev/null
task_encryption_rollback
[[ -z "${CALLS}" ]]
printf '%s\n' 'ok - unencrypted mode uses the system partition without passphrase or mapping'

LUKS_ENABLED=true
[[ "$(root_block_device)" == /dev/mapper/cryptroot ]]
task_encryption_validate
[[ "${CALLS}" == 'confirm ' ]]
printf '%s\n' 'ok - encrypted mode retains explicit confirmation'

TPM2_ENABLED=true
LUKS_ENABLED=false
if task_encryption_validate >/dev/null 2>&1; then
    printf '%s\n' 'not ok - TPM2 was accepted without LUKS' >&2
    exit 1
fi
printf '%s\n' 'ok - TPM2 without LUKS is rejected'
