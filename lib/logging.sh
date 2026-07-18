```bash
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

info() {
    printf '%b[INFO]%b %s\n' "${LOG_BLUE}" "${LOG_RESET}" "$*"
}

success() {
    printf '%b[OK]%b %s\n' "${LOG_GREEN}" "${LOG_RESET}" "$*"
}

warn() {
    printf '%b[WARN]%b %s\n' "${LOG_YELLOW}" "${LOG_RESET}" "$*" >&2
}

error() {
    printf '%b[ERROR]%b %s\n' "${LOG_RED}" "${LOG_RESET}" "$*" >&2
}

fatal() {
    error "$*"
    exit 1
}

section() {
    printf '\n%b%s%b\n' "${LOG_BOLD}" "$*" "${LOG_RESET}"
}
```
