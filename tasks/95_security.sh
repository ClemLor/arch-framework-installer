#!/usr/bin/env bash

task_security_name() { printf 'Security and TPM2'; }
task_security_validate() {
    [[ "${TPM2_ENABLED}" != "true" ]] || require_commands_for_mode "TPM2" systemd-cryptenroll
}
task_security_execute() { enroll_luks_tpm2 && run_in_chroot systemctl enable fstrim.timer fwupd-refresh.timer; }
task_security_verify() {
    [[ "${DRY_RUN}" == "true" || "${TPM2_ENABLED}" != "true" ]] && return 0
    systemd-cryptenroll "$(luks_device)" | grep -q 'tpm2'
}
task_security_cleanup() { return 0; }
task_security_rollback() { warn "TPM2 enrollment is not removed automatically; keep the recovery passphrase."; return 0; }
