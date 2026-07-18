#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
readonly ROOT

MOUNT_ROOT="/target"
DRY_RUN="false"
WRITES=''
COMMANDS=''

write_target_file() {
    WRITES+="PATH:$1
$2
"
}

run_command() {
    COMMANDS+="$*
"
}

info() { :; }

# shellcheck source=lib/memory.sh
source "${ROOT}/lib/memory.sh"

ZRAM_ENABLED="true"
configure_zram
[[ "${WRITES}" == *'PATH:/etc/systemd/zram-generator.conf'* ]]
[[ "${WRITES}" == *'zram-size = ram / 2'* ]]
[[ "${WRITES}" == *'compression-algorithm = zstd'* ]]
[[ -z "${COMMANDS}" ]]
printf '%s\n' 'ok - enabled zram writes the generator configuration'

ZRAM_ENABLED="false"
WRITES=''
COMMANDS=''
configure_zram
[[ -z "${WRITES}" ]]
[[ "${COMMANDS}" == *'rm -f /target/etc/systemd/zram-generator.conf'* ]]
printf '%s\n' 'ok - disabled zram removes only the installer-managed configuration'
