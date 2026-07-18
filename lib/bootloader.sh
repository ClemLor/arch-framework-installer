#!/usr/bin/env bash

if [[ -n "${ARCH_INSTALLER_BOOTLOADER_LOADED:-}" ]]; then return 0; fi
readonly ARCH_INSTALLER_BOOTLOADER_LOADED="true"

limine_kernel_command_line() {
    local root_identifier="$1"

    if [[ "${LUKS_ENABLED}" == "true" ]]; then
        printf 'rd.luks.name=%s=%s ' "${root_identifier}" "${LUKS_NAME}"
        if [[ "${TPM2_ENABLED}" == "true" ]]; then
            printf 'rd.luks.options=%s=tpm2-device=auto ' "${root_identifier}"
        fi
        printf 'root=/dev/mapper/%s rootflags=subvol=@ rw' "${LUKS_NAME}"
        return
    fi

    printf 'root=PARTUUID=%s rootflags=subvol=@ rw' "${root_identifier}"
}

configure_limine_efi_updates() {
    write_target_file /usr/local/lib/arch-framework-installer/update-limine-efi '#!/usr/bin/env bash
set -Eeuo pipefail

source_path="/usr/share/limine/BOOTX64.EFI"
test -s "${source_path}"
install -Dm0644 "${source_path}" /boot/EFI/arch-limine/BOOTX64.EFI
install -Dm0644 "${source_path}" /boot/EFI/BOOT/BOOTX64.EFI
' || return 1
    run_command chmod 0755 "${MOUNT_ROOT}/usr/local/lib/arch-framework-installer/update-limine-efi" || return 1
    write_target_file /etc/pacman.d/hooks/95-limine-efi.hook '[Trigger]
Operation = Install
Operation = Upgrade
Type = Package
Target = limine

[Action]
Description = Deploying the updated Limine UEFI executable
When = PostTransaction
Exec = /usr/local/lib/arch-framework-installer/update-limine-efi
'
}

install_limine() {
    local root_identifier
    local kernel_command_line
    local configuration

    if [[ "${LUKS_ENABLED}" == "true" ]]; then
        if [[ "${DRY_RUN:-false}" == "true" ]]; then
            root_identifier="DRY-RUN-LUKS-UUID"
        else
            root_identifier="$(cryptsetup luksUUID "$(luks_device)")" || return 1
        fi
    else
        if [[ "${DRY_RUN:-false}" == "true" ]]; then
            root_identifier="DRY-RUN-PARTUUID"
        else
            root_identifier="$(blkid -s PARTUUID -o value "$(get_system_partition_path)")" || return 1
            [[ -n "${root_identifier}" ]] || { error "Unable to read the root partition PARTUUID."; return 1; }
        fi
    fi

    kernel_command_line="$(limine_kernel_command_line "${root_identifier}")" || return 1

    configuration="timeout: 5
default_entry: 1

/Arch Linux LTS
    protocol: linux
    kernel_path: boot():/vmlinuz-${DEFAULT_KERNEL}
    module_path: boot():/initramfs-${DEFAULT_KERNEL}.img
    kernel_cmdline: ${kernel_command_line}

/Arch Linux fallback
    protocol: linux
    kernel_path: boot():/vmlinuz-${FALLBACK_KERNEL}
    module_path: boot():/initramfs-${FALLBACK_KERNEL}.img
    kernel_cmdline: ${kernel_command_line}
"
    write_target_file /boot/limine.conf "${configuration}" || return 1
    configure_limine_efi_updates || return 1
    run_in_chroot mkinitcpio -P || return 1
    run_in_chroot /usr/local/lib/arch-framework-installer/update-limine-efi
}

verify_limine() {
    local config_path="${MOUNT_ROOT}/boot/limine.conf"
    local efi_source="${MOUNT_ROOT}/usr/share/limine/BOOTX64.EFI"

    [[ "${DRY_RUN:-false}" == "true" ]] && return 0
    [[ -s "${efi_source}" ]] &&
        cmp -s "${efi_source}" "${MOUNT_ROOT}/boot/EFI/arch-limine/BOOTX64.EFI" &&
        cmp -s "${efi_source}" "${MOUNT_ROOT}/boot/EFI/BOOT/BOOTX64.EFI" &&
        [[ -s "${config_path}" ]] &&
        [[ -s "${MOUNT_ROOT}/boot/vmlinuz-${DEFAULT_KERNEL}" ]] &&
        [[ -s "${MOUNT_ROOT}/boot/initramfs-${DEFAULT_KERNEL}.img" ]] &&
        [[ -s "${MOUNT_ROOT}/boot/vmlinuz-${FALLBACK_KERNEL}" ]] &&
        [[ -s "${MOUNT_ROOT}/boot/initramfs-${FALLBACK_KERNEL}.img" ]] &&
        [[ -x "${MOUNT_ROOT}/usr/local/lib/arch-framework-installer/update-limine-efi" ]] &&
        [[ -s "${MOUNT_ROOT}/etc/pacman.d/hooks/95-limine-efi.hook" ]] &&
        grep -Fq "/Arch Linux LTS" "${config_path}" &&
        grep -Fq "/Arch Linux fallback" "${config_path}" &&
        grep -Fq "kernel_path: boot():/vmlinuz-${DEFAULT_KERNEL}" "${config_path}" &&
        grep -Fq "kernel_path: boot():/vmlinuz-${FALLBACK_KERNEL}" "${config_path}"
}
