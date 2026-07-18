#!/usr/bin/env bash

if [[ -n "${ARCH_INSTALLER_BOOTLOADER_LOADED:-}" ]]; then return 0; fi
readonly ARCH_INSTALLER_BOOTLOADER_LOADED="true"

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
        kernel_command_line="rd.luks.name=${root_identifier}=${LUKS_NAME} root=/dev/mapper/${LUKS_NAME} rootflags=subvol=@ rw"
    else
        if [[ "${DRY_RUN:-false}" == "true" ]]; then
            root_identifier="DRY-RUN-PARTUUID"
        else
            root_identifier="$(blkid -s PARTUUID -o value "$(get_system_partition_path)")" || return 1
            [[ -n "${root_identifier}" ]] || { error "Unable to read the root partition PARTUUID."; return 1; }
        fi
        kernel_command_line="root=PARTUUID=${root_identifier} rootflags=subvol=@ rw"
    fi

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
    run_command mkdir -p "${MOUNT_ROOT}/boot/EFI/arch-limine" "${MOUNT_ROOT}/boot/EFI/BOOT" || return 1
    run_command cp "${MOUNT_ROOT}/usr/share/limine/BOOTX64.EFI" "${MOUNT_ROOT}/boot/EFI/arch-limine/BOOTX64.EFI" || return 1
    run_command cp "${MOUNT_ROOT}/usr/share/limine/BOOTX64.EFI" "${MOUNT_ROOT}/boot/EFI/BOOT/BOOTX64.EFI" || return 1
    write_target_file /boot/limine.conf "${configuration}" || return 1
    run_in_chroot mkinitcpio -P
}

verify_limine() {
    [[ "${DRY_RUN:-false}" == "true" ]] && return 0
    [[ -s "${MOUNT_ROOT}/boot/EFI/arch-limine/BOOTX64.EFI" ]] &&
        [[ -s "${MOUNT_ROOT}/boot/limine.conf" ]] &&
        [[ -s "${MOUNT_ROOT}/boot/vmlinuz-${DEFAULT_KERNEL}" ]] &&
        [[ -s "${MOUNT_ROOT}/boot/initramfs-${DEFAULT_KERNEL}.img" ]]
}
