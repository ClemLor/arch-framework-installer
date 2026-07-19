#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
readonly ROOT
source "${ROOT}/lib/logging.sh"
source "${ROOT}/lib/common.sh"
source "${ROOT}/lib/commands.sh"
source "${ROOT}/lib/pacstraps.sh"
source "${ROOT}/lib/packages.sh"

if collect_packages | grep -Fxq nano; then
    printf '%s\n' 'ok - nano is included for TTY recovery'
else
    printf '%s\n' 'not ok - nano is missing from the package set' >&2
    exit 1
fi

for package in cava cups-pk-helper dms-shell-niri intel-media-driver \
    kimageformats matugen niri vulkan-intel; do
    if ! collect_packages | grep -Fxq "${package}"; then
        printf 'not ok - required Niri/DMS package is missing: %s\n' "${package}" >&2
        exit 1
    fi
done
printf '%s\n' 'ok - Niri, DMS and Framework graphics packages are included'

collect_packages() { printf '%s\n' base unavailable-package; }
pacman() {
    [[ "${*: -1}" != "unavailable-package" ]]
}

if validate_configured_packages_available >/dev/null 2>&1; then
    printf '%s\n' 'not ok - unavailable package passed preflight' >&2
    exit 1
fi
printf '%s\n' 'ok - unavailable package fails before storage operations'

collect_packages() { printf '%s\n' base linux; }
validate_configured_packages_available >/dev/null
printf '%s\n' 'ok - available repository packages pass preflight'

CALLS=''
collect_packages() { printf '%s\n' base nano; }
run_in_chroot() { CALLS+="$*\n"; }
verify_required_packages
[[ "${CALLS}" == *'pacman -Q base'* ]]
[[ "${CALLS}" == *'pacman -Q nano'* ]]
printf '%s\n' 'ok - every collected package is verified in the target'
