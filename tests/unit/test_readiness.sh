#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
readonly ROOT
source "${ROOT}/lib/logging.sh"
source "${ROOT}/lib/verify.sh"

DRY_RUN=false
HOSTNAME=framework
LUKS_ENABLED=true
TARGET_FIXTURE="$(mktemp -d)"
readonly TARGET_FIXTURE
trap 'rm -r "${TARGET_FIXTURE}"' EXIT
MOUNT_ROOT="${TARGET_FIXTURE}"
mkdir -p \
    "${MOUNT_ROOT}/etc/sudoers.d" \
    "${MOUNT_ROOT}/etc/snapper/configs"
# genfstab writes the Btrfs subvolume with a leading slash.
printf 'UUID=root / btrfs rw,noatime,subvolid=256,subvol=/@ 0 0\nUUID=efi /boot vfat defaults 0 2\n' >"${MOUNT_ROOT}/etc/fstab"
printf 'framework\n' >"${MOUNT_ROOT}/etc/hostname"
printf 'LANG=en_US.UTF-8\n' >"${MOUNT_ROOT}/etc/locale.conf"
printf 'KEYMAP=us\n' >"${MOUNT_ROOT}/etc/vconsole.conf"
printf 'HOOKS=(base systemd sd-encrypt filesystems)\n' >"${MOUNT_ROOT}/etc/mkinitcpio.conf"
printf '%%wheel ALL=(ALL:ALL) ALL\n' >"${MOUNT_ROOT}/etc/sudoers.d/10-wheel"
printf 'SUBVOLUME="/"\n' >"${MOUNT_ROOT}/etc/snapper/configs/root"

verify_core_target_configuration
printf 'UUID=root / btrfs rw,noatime,subvol=/@home 0 0\nUUID=efi /boot vfat defaults 0 2\n' >"${MOUNT_ROOT}/etc/fstab"
if verify_core_target_configuration >/dev/null 2>&1; then
    printf '%s\n' 'not ok - a non-root Btrfs subvolume passed core readiness' >&2
    exit 1
fi
printf 'UUID=root / btrfs rw,noatime,subvol=@ 0 0\nUUID=efi /boot vfat defaults 0 2\n' >"${MOUNT_ROOT}/etc/fstab"
LUKS_ENABLED=false
printf 'HOOKS=(base systemd filesystems)\n' >"${MOUNT_ROOT}/etc/mkinitcpio.conf"
verify_core_target_configuration
printf '%s\n' 'ok - core readiness accepts genfstab root syntax and both encryption profiles'

CALLS=""
FAIL_CHECK=""

record_check() {
    CALLS+="$1 "
    [[ "${FAIL_CHECK}" != "$1" ]]
}

verify_target_mounts() { record_check mounts; }
verify_core_target_configuration() { record_check core; }
verify_required_packages() { record_check packages; }
verify_enabled_services() { record_check services; }
verify_installed_user() { record_check user; }
verify_zram_configuration() { record_check zram; }
verify_graphical_session() { record_check graphical; }
verify_limine() { record_check boot; }
verify_installed_security() { record_check security; }

verify_installation_readiness >/dev/null
[[ "${CALLS}" == 'mounts core packages services user zram graphical boot security ' ]]
printf '%s\n' 'ok - final readiness runs every critical check before cleanup'

CALLS=""
FAIL_CHECK=services
if verify_installation_readiness >/dev/null 2>&1; then
    printf '%s\n' 'not ok - final readiness accepted a failed service check' >&2
    exit 1
fi
[[ "${CALLS}" == 'mounts core packages services ' ]]
printf '%s\n' 'ok - final readiness stops at the first actionable failure'

DRY_RUN=true
CALLS=""
verify_installation_readiness >/dev/null
[[ -z "${CALLS}" ]]
printf '%s\n' 'ok - dry-run does not inspect a nonexistent target installation'
