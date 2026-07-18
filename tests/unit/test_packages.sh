#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
readonly ROOT
source "${ROOT}/lib/logging.sh"
source "${ROOT}/lib/common.sh"
source "${ROOT}/lib/commands.sh"
source "${ROOT}/lib/pacstraps.sh"

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
