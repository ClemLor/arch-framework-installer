#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
readonly ROOT
source "${ROOT}/lib/logging.sh"
source "${ROOT}/lib/luks.sh"

LUKS_ENABLED=true
TPM2_ENABLED=true
DRY_RUN=false
LUKS_NAME=cryptroot
TOKEN_PRESENT=true
CALL_LOG="$(mktemp)"
readonly CALL_LOG
trap 'rm -f "${CALL_LOG}"' EXIT

get_system_partition_path() { printf /dev/mock2; }
capture_logged_command() {
    printf 'capture:%s\n' "$*" >>"${CALL_LOG}"
    case "$1" in
        cryptsetup)
            printf '{"tokens":{"0":{"type":"systemd-tpm2"}}}\n'
            ;;
        jq)
            [[ "${TOKEN_PRESENT}" == "true" ]]
            ;;
    esac
}
run_command() { printf 'run:%s\n' "$*" >>"${CALL_LOG}"; }

luks_has_tpm2_token
CALLS="$(<"${CALL_LOG}")"
[[ "${CALLS}" == *'capture:cryptsetup luksDump --dump-json-metadata /dev/mock2'* ]]
[[ "${CALLS}" == *'capture:jq --exit-status any(.tokens[]?; .type == "systemd-tpm2")'* ]]
printf '%s\n' 'ok - TPM2 tokens are checked through LUKS2 JSON metadata'

: >"${CALL_LOG}"
enroll_luks_tpm2
CALLS="$(<"${CALL_LOG}")"
[[ "${CALLS}" != *'run:systemd-cryptenroll'* ]]
printf '%s\n' 'ok - an existing TPM2 token is not duplicated'

TOKEN_PRESENT=false
: >"${CALL_LOG}"
enroll_luks_tpm2
CALLS="$(<"${CALL_LOG}")"
[[ "${CALLS}" == *'run:systemd-cryptenroll --tpm2-device=auto --tpm2-pcrs=7 /dev/mock2'* ]]
printf '%s\n' 'ok - TPM2 enrollment uses the documented PCR 7 policy'

DRY_RUN=true
: >"${CALL_LOG}"
enroll_luks_tpm2
CALLS="$(<"${CALL_LOG}")"
[[ "${CALLS}" != *'capture:'* ]]
[[ "${CALLS}" == *'run:systemd-cryptenroll --tpm2-device=auto --tpm2-pcrs=7 /dev/mock2'* ]]
printf '%s\n' 'ok - dry-run renders enrollment without inspecting a real volume'
