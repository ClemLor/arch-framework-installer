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
error() { :; }
success() { :; }

# shellcheck source=lib/memory.sh
source "${ROOT}/lib/memory.sh"

ZRAM_ENABLED="true"
configure_zram
[[ "${WRITES}" == *'PATH:/etc/systemd/zram-generator.conf'* ]]
[[ "${WRITES}" == *'zram-size = ram / 2'* ]]
[[ "${WRITES}" == *'compression-algorithm = zstd'* ]]
[[ -z "${COMMANDS}" ]]
printf '%s\n' 'ok - enabled zram writes the generator configuration'

# This is why zram appeared to do nothing: the default swappiness of 60 is tuned
# for swap on a disk, so the kernel reclaims page cache rather than using zram.
[[ "${WRITES}" == *'PATH:/etc/sysctl.d/99-zram.conf'* ]]
[[ "${WRITES}" == *'vm.swappiness = 180'* ]]
[[ "${WRITES}" == *'vm.page-cluster = 0'* ]]
printf '%s\n' 'ok - enabled zram tunes the kernel for RAM-speed swap'

# zram must outrank the swapfile, or everyday paging is striped onto disk and the
# swapfile stops being reserved for hibernation.
[[ "${WRITES}" == *"swap-priority = ${ZRAM_SWAP_PRIORITY}"* ]]
(( ZRAM_SWAP_PRIORITY > SWAPFILE_SWAP_PRIORITY ))
printf '%s\n' 'ok - zram outranks the hibernation swapfile'

ZRAM_ENABLED="false"
WRITES=''
COMMANDS=''
configure_zram
[[ -z "${WRITES}" ]]
[[ "${COMMANDS}" == *'rm -f /target/etc/systemd/zram-generator.conf'* ]]
[[ "${COMMANDS}" == *'rm -f /target/etc/sysctl.d/99-zram.conf'* ]]
printf '%s\n' 'ok - disabled zram removes only the installer-managed configuration'
