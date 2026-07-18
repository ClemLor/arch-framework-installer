#!/usr/bin/env bash

task_security_name() { printf 'Security and TPM2'; }
task_security_validate() {
    if [[ "${TPM2_ENABLED}" == "true" ]]; then
        validate_tpm2_hardware || return 1
        require_commands_for_mode "TPM2" cryptsetup jq systemd-cryptenroll
    fi
}
task_security_execute() { enroll_luks_tpm2; }
task_security_verify() {
    [[ "${DRY_RUN}" == "true" || "${TPM2_ENABLED}" != "true" ]] && return 0
    if ! luks_has_tpm2_token; then
        error "No systemd TPM2 token was found in the LUKS2 metadata."
        return 1
    fi
}
task_security_cleanup() { return 0; }
task_security_rollback() { warn "TPM2 enrollment is not removed automatically; keep the recovery passphrase."; return 0; }
