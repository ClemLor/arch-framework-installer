#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
readonly ROOT
source "${ROOT}/lib/logging.sh"
source "${ROOT}/lib/common.sh"
source "${ROOT}/lib/validation.sh"

FIXTURE="$(mktemp -d)"
trap 'rm -r "${FIXTURE}"' EXIT
EFI_SYSFS_ROOT="${FIXTURE}/efi"
mkdir -p "${EFI_SYSFS_ROOT}"

printf '64\n' >"${EFI_SYSFS_ROOT}/fw_platform_size"
is_uefi_system
[[ "$(get_uefi_platform_size)" == "64" ]]
printf '%s\n' 'ok - 64-bit UEFI platform file is detected'

rm "${EFI_SYSFS_ROOT}/fw_platform_size"
mkdir -p "${EFI_SYSFS_ROOT}/efivars"
is_uefi_system
[[ "$(get_uefi_platform_size)" == "unknown" ]]
printf '%s\n' 'ok - UEFI remains detected when efivarfs metadata is unavailable'

rmdir "${EFI_SYSFS_ROOT}/efivars" "${EFI_SYSFS_ROOT}"
if is_uefi_system; then
    printf '%s\n' 'not ok - missing EFI sysfs was accepted' >&2
    exit 1
fi
printf '%s\n' 'ok - missing EFI sysfs is rejected as BIOS/CSM'
