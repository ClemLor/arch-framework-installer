#!/usr/bin/env bash

# ==============================================================================
# Module: logging
#
# Purpose:
#   Provide consistent logging functions for all project scripts.
#
# Idempotent:
#   Yes
# ==============================================================================

if [[ -n "${ARCH_INSTALLER_LOGGING_LOADED:-}" ]]; then
    return 0
fi

readonly ARCH_INSTALLER_LOGGING_LOADED="true"

readonly LOG_RESET='\033[0m'
readonly LOG_BLUE='\033[0;34m'
readonly LOG_GREEN='\033[0;32m'
readonly LOG_YELLOW='\033[0;33m'
readonly LOG_RED='\033[0;31m'
readonly LOG_BOLD='\033[1m'

LOG_FILE="${LOG_FILE:-}"

init_logging() {
    local root="${1:-$(project_root)}"
    local log_dir="${root}/logs"

    mkdir -p "${log_dir}" || return 1
    LOG_FILE="${LOG_FILE:-${log_dir}/$(date -u '+%Y-%m-%d-%H-%M-%S')-install.log}"
    : >"${LOG_FILE}" || return 1
    export LOG_FILE
}

log_message() {
    local level="$1"
    shift

    if [[ -n "${LOG_FILE}" ]]; then
        printf '%s [%s] %s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" "${level}" "$*" >>"${LOG_FILE}"
    fi
}

info() {
    log_message "INFO" "$*"
    printf '%b[INFO]%b %s\n' "${LOG_BLUE}" "${LOG_RESET}" "$*"
}

success() {
    log_message "OK" "$*"
    printf '%b[OK]%b %s\n' "${LOG_GREEN}" "${LOG_RESET}" "$*"
}

warn() {
    log_message "WARN" "$*"
    printf '%b[WARN]%b %s\n' "${LOG_YELLOW}" "${LOG_RESET}" "$*" >&2
}

error() {
    log_message "ERROR" "$*"
    printf '%b[ERROR]%b %s\n' "${LOG_RED}" "${LOG_RESET}" "$*" >&2
}

fatal() {
    error "$*"
    exit 1
}

section() {
    log_message "SECTION" "$*"
    printf '\n%b%s%b\n' "${LOG_BOLD}" "$*" "${LOG_RESET}"
}
