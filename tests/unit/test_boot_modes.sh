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
TPM2_ENABLED=false
CONFIGURATION=""
run_command() { return 0; }
run_in_chroot() { return 0; }
write_target_file() {
    if [[ "$1" == /boot/limine.conf ]]; then
        CONFIGURATION="$2"
    fi
}
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

TPM2_ENABLED=true
CONFIGURATION=""
install_limine
[[ "${CONFIGURATION}" == *'rd.luks.options=DRY-RUN-LUKS-UUID=tpm2-device=auto'* ]]
printf '%s\n' 'ok - TPM2 enrollment is activated from the kernel command line'

DRY_RUN=false
TPM2_ENABLED=false
BOOT_FIXTURE="$(mktemp -d)"
trap 'rm -r "${BOOT_FIXTURE}"' EXIT
MOUNT_ROOT="${BOOT_FIXTURE}"
mkdir -p \
    "${MOUNT_ROOT}/usr/share/limine" \
    "${MOUNT_ROOT}/boot/EFI/arch-limine" \
    "${MOUNT_ROOT}/boot/EFI/BOOT" \
    "${MOUNT_ROOT}/usr/local/lib/arch-framework-installer" \
    "${MOUNT_ROOT}/etc/pacman.d/hooks"
printf 'efi\n' >"${MOUNT_ROOT}/usr/share/limine/BOOTX64.EFI"
cp "${MOUNT_ROOT}/usr/share/limine/BOOTX64.EFI" "${MOUNT_ROOT}/boot/EFI/arch-limine/BOOTX64.EFI"
cp "${MOUNT_ROOT}/usr/share/limine/BOOTX64.EFI" "${MOUNT_ROOT}/boot/EFI/BOOT/BOOTX64.EFI"
printf 'kernel\n' >"${MOUNT_ROOT}/boot/vmlinuz-${DEFAULT_KERNEL}"
printf 'initramfs\n' >"${MOUNT_ROOT}/boot/initramfs-${DEFAULT_KERNEL}.img"
printf 'kernel\n' >"${MOUNT_ROOT}/boot/vmlinuz-${FALLBACK_KERNEL}"
printf 'initramfs\n' >"${MOUNT_ROOT}/boot/initramfs-${FALLBACK_KERNEL}.img"
printf '/Arch Linux LTS\n    kernel_path: boot():/vmlinuz-linux-lts\n/Arch Linux fallback\n    kernel_path: boot():/vmlinuz-linux\n' >"${MOUNT_ROOT}/boot/limine.conf"
printf 'hook\n' >"${MOUNT_ROOT}/etc/pacman.d/hooks/95-limine-efi.hook"
printf '#!/usr/bin/env bash\n' >"${MOUNT_ROOT}/usr/local/lib/arch-framework-installer/update-limine-efi"
chmod 0755 "${MOUNT_ROOT}/usr/local/lib/arch-framework-installer/update-limine-efi"
verify_limine
printf '%s\n' 'ok - both kernels and both Limine EFI paths are verified'
