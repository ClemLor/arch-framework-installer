#!/usr/bin/env bash

if [[ -n "${ARCH_INSTALLER_VERIFY_LOADED:-}" ]]; then return 0; fi
readonly ARCH_INSTALLER_VERIFY_LOADED="true"

verify_target_file() {
    [[ "${DRY_RUN:-false}" == "true" ]] || [[ -s "${MOUNT_ROOT}$1" ]]
}

verify_core_target_configuration() {
    local fstab_path="${MOUNT_ROOT}/etc/fstab"
    local mkinitcpio_path="${MOUNT_ROOT}/etc/mkinitcpio.conf"

    verify_target_file /etc/fstab || return 1
    verify_target_file /etc/hostname || return 1
    verify_target_file /etc/locale.conf || return 1
    verify_target_file /etc/vconsole.conf || return 1
    verify_target_file /etc/mkinitcpio.conf || return 1
    verify_target_file /etc/sudoers.d/10-wheel || return 1
    verify_target_file /etc/snapper/configs/root || return 1
    [[ "$(<"${MOUNT_ROOT}/etc/hostname")" == "${HOSTNAME}" ]] || return 1
    grep -Fq 'subvol=@' "${fstab_path}" || return 1
    grep -Fq '/boot' "${fstab_path}" || return 1
    if [[ "${LUKS_ENABLED}" == "true" ]]; then
        grep -Fq 'sd-encrypt' "${mkinitcpio_path}"
    else
        ! grep -Fq 'sd-encrypt' "${mkinitcpio_path}"
    fi
}

verify_installed_user() {
    run_in_chroot id "${USERNAME}" >/dev/null || return 1
    run_in_chroot visudo -cf /etc/sudoers.d/10-wheel >/dev/null || return 1
    verify_user_desktop
}

verify_installed_security() {
    verify_luks || return 1
    if [[ "${TPM2_ENABLED}" == "true" ]]; then
        luks_has_tpm2_token
    fi
}

verify_readiness_check() {
    local description="$1"
    shift

    if ! "$@"; then
        error "Final readiness check failed: ${description}."
        return 1
    fi
    success "Final readiness check passed: ${description}."
}

verify_installation_readiness() {
    if [[ "${DRY_RUN:-false}" == "true" ]]; then
        info "Final readiness checks are not executed against the target in dry-run."
        return 0
    fi

    verify_readiness_check "target filesystems are mounted" verify_target_mounts || return 1
    verify_readiness_check "core configuration is complete" verify_core_target_configuration || return 1
    verify_readiness_check "configured packages are installed" verify_required_packages || return 1
    verify_readiness_check "system services are enabled" verify_enabled_services || return 1
    verify_readiness_check "the user and desktop session are configured" verify_installed_user || return 1
    verify_readiness_check "zram matches the selected profile" verify_zram_configuration || return 1
    verify_readiness_check "the graphical login is configured" verify_graphical_session || return 1
    verify_readiness_check "Limine and boot artifacts are complete" verify_limine || return 1
    verify_readiness_check "the storage security profile is valid" verify_installed_security
}
