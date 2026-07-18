#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
readonly ROOT
source "${ROOT}/lib/partition.sh"
source "${ROOT}/tasks/10_storage.sh"

TESTS=0
FAILURES=0
DRY_RUN=true
TARGET_DISK=/dev/mockdisk
CALLS=""

assert_equal() {
    local expected="$1" actual="$2" message="$3"
    ((TESTS += 1))
    if [[ "${expected}" == "${actual}" ]]; then printf 'ok - %s\n' "${message}"; else printf 'not ok - %s\n' "${message}" >&2; ((FAILURES += 1)); fi
}

validate_storage_plan() { return 0; }
show_storage_plan() { CALLS+="plan "; }
show_planned_partition_layout() { CALLS+="layout "; }
confirm_destructive_action() { CALLS+="confirm:$1 "; return 0; }
create_partition_table() { CALLS+="partition "; }
wait_for_partition_devices() { CALLS+="wait "; }
verify_partition_table() { CALLS+="verify "; }
run_command() { CALLS+="command:$* "; }
warn() { :; }
error() { :; }

task_storage_validate
task_storage_execute
task_storage_verify
task_storage_cleanup
assert_equal 'layout partition wait verify ' "${CALLS}" 'dry-run uses mocked plan without confirmation or physical commands'

DRY_RUN=false
CALLS=""
STORAGE_CONFIRMED=false
task_storage_validate
assert_equal 'plan confirm:/dev/mockdisk ' "${CALLS}" 'real mode confirms the complete target path'

DRY_RUN=false
EFI_SIZE=1GiB
EFI_PARTITION_LABEL=EFI
SYSTEM_PARTITION_LABEL=ARCH
get_efi_partition_path() { printf /dev/mockdisk1; }
get_system_partition_path() { printf /dev/mockdisk2; }
sgdisk() { return 0; }
get_disk_partition_table() { printf gpt; }
get_disk_partition_count() { printf 2; }
get_partition_type_guid() {
    [[ "$1" == /dev/mockdisk1 ]] && printf c12a7328-f81f-11d2-ba4b-00a0c93ec93b || printf ca7d7ccb-63ed-4c53-861c-1742536059cc
}
get_partition_label() { [[ "$1" == /dev/mockdisk1 ]] && printf EFI || printf ARCH; }
get_disk_size_bytes() {
    case "$1" in
        /dev/mockdisk) printf 107374182400 ;;
        /dev/mockdisk1) printf 1073741824 ;;
        /dev/mockdisk2) printf 106299342848 ;;
    esac
}
is_partition_mib_aligned() { return 0; }
if verify_partition_table; then
    assert_equal verified verified 'GPT type, labels, sizes and alignment are verified through mocks'
else
    assert_equal verified failed 'GPT type, labels, sizes and alignment are verified through mocks'
fi

printf '%d tests, %d failures\n' "${TESTS}" "${FAILURES}"
((FAILURES == 0))
