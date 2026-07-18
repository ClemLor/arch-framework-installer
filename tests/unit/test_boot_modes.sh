#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
readonly ROOT
source "${ROOT}/lib/logging.sh"
source "${ROOT}/lib/bootloader.sh"

DRY_RUN=true
MOUNT_ROOT=/mnt
DEFAULT_KERNEL=linux-lts
FALLBACK_KERNEL=linux
LUKS_NAME=cryptroot
CONFIGURATION=""
run_command() { return 0; }
run_in_chroot() { return 0; }
write_target_file() { [[ "$1" == /boot/limine.conf ]] && CONFIGURATION="$2"; }
get_system_partition_path() { printf /dev/mock2; }
luks_device() { get_system_partition_path; }

LUKS_ENABLED=false
install_limine
[[ "${CONFIGURATION}" == *'root=PARTUUID=DRY-RUN-PARTUUID'* ]]
[[ "${CONFIGURATION}" != *'rd.luks.name='* ]]
printf '%s\n' 'ok - unencrypted Limine entry uses the root PARTUUID'

LUKS_ENABLED=true
CONFIGURATION=""
install_limine
[[ "${CONFIGURATION}" == *'rd.luks.name=DRY-RUN-LUKS-UUID=cryptroot'* ]]
printf '%s\n' 'ok - encrypted Limine entry retains the LUKS mapping'
