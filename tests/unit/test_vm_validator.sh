#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
readonly ROOT
export VM_VALIDATOR_LIBRARY_ONLY=true
source "${ROOT}/tests/vm/validate_installation.sh"

parse_arguments \
    --user reaper \
    --encryption enabled \
    --tpm2 disabled \
    --zram enabled
[[ "${TARGET_USERNAME}" == "reaper" ]]
[[ "${ENCRYPTION_PROFILE}" == "enabled" ]]
[[ "${TPM2_PROFILE}" == "disabled" ]]
[[ "${ZRAM_PROFILE}" == "enabled" ]]
printf '%s\n' 'ok - VM validation profiles are parsed explicitly'

MOCK_ZRAM_ACTIVE=true
swapon() { printf '{"swapdevices":[]}\n'; }
jq() { [[ "${MOCK_ZRAM_ACTIVE}" == "true" ]]; }

validate_zram_profile
MOCK_ZRAM_ACTIVE=false
ZRAM_PROFILE=disabled
validate_zram_profile
printf '%s\n' 'ok - VM validation enforces enabled and disabled zram profiles'

FAILURES=0
record_check success true >/dev/null
record_check failure false >/dev/null 2>&1
[[ "${FAILURES}" -eq 1 ]]
printf '%s\n' 'ok - VM validation aggregates failed checks'

find() { printf '/dev/dri/renderD128\n'; }
grep() { command grep "$@"; }
graphics_render_node_available
find() { return 0; }
! graphics_render_node_available
printf '%s\n' 'ok - VM validation detects a missing DRM render node'

VALIDATOR_SOURCE="$(<"${ROOT}/tests/vm/validate_installation.sh")"
[[ "${VALIDATOR_SOURCE}" != *'lsblk niri pacman'* ]]
[[ "${VALIDATOR_SOURCE}" == *'command -v niri'* ]]
printf '%s\n' 'ok - a missing Niri installation fails one check without aborting validation'
