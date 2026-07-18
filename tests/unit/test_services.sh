#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
readonly ROOT

DRY_RUN="false"
CALLS=''

project_root() { printf '%s' "${ROOT}"; }
run_in_chroot() { CALLS+="$*\n"; }

# shellcheck source=lib/services.sh
source "${ROOT}/lib/services.sh"

configure_services
[[ "${CALLS}" == *'systemctl enable NetworkManager.service'* ]]
[[ "${CALLS}" == *'systemctl enable fwupd-refresh.timer'* ]]
[[ "${CALLS}" == *'systemctl enable snapper-timeline.timer'* ]]
printf '%s\n' 'ok - configured services are enabled from the central registry'

CALLS=''
verify_enabled_services
[[ "${CALLS}" == *'systemctl is-enabled --quiet NetworkManager.service'* ]]
[[ "${CALLS}" == *'systemctl is-enabled --quiet fwupd-refresh.timer'* ]]
printf '%s\n' 'ok - enabled services are verified after configuration'
