#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
readonly ROOT
source "${ROOT}/lib/logging.sh"
source "${ROOT}/lib/common.sh"
source "${ROOT}/lib/system.sh"

FIXTURE="$(mktemp -d)"
trap 'rm -r "${FIXTURE}"' EXIT
TPM_DEVICE_ROOT="${FIXTURE}/dev"
TPM_SYSFS_ROOT="${FIXTURE}/sys/class/tpm"
mkdir -p "${TPM_DEVICE_ROOT}" "${TPM_SYSFS_ROOT}/tpm0"

if has_tpm2_device; then
    printf '%s\n' 'not ok - missing TPM device was accepted' >&2
    exit 1
fi
printf '%s\n' 'ok - missing TPM device is rejected'

: >"${TPM_DEVICE_ROOT}/tpmrm0"
printf '2\n' >"${TPM_SYSFS_ROOT}/tpm0/tpm_version_major"
has_tpm2_device
printf '%s\n' 'ok - TPM 2.0 resource manager is detected'

printf '1\n' >"${TPM_SYSFS_ROOT}/tpm0/tpm_version_major"
if has_tpm2_device; then
    printf '%s\n' 'not ok - TPM 1.x was accepted as TPM2' >&2
    exit 1
fi
printf '%s\n' 'ok - TPM 1.x is rejected'
