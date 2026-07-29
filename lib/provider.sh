#!/usr/bin/env bash

# ==============================================================================
# Module: provider
#
# Purpose:
#   Dispatch to an implementation chosen by name, so a component can be replaced
#   without editing the code that uses it.
#
# The convention is the one the task engine already uses:
#
#   task_<id>_<phase>          tasks
#   bootloader_<name>_<phase>  bootloaders
#   desktop_<name>_<phase>     desktop sessions
#
# Adding a bootloader means adding bootloader_<name>_* functions and listing the
# name; nothing that calls it changes. The alternative — a case statement in each
# call site — puts the knowledge of which options exist in several places, and
# they drift.
#
# Idempotent:
#   Yes
# ==============================================================================

if [[ -n "${ARCH_INSTALLER_PROVIDER_LOADED:-}" ]]; then return 0; fi
readonly ARCH_INSTALLER_PROVIDER_LOADED="true"

# Every implementation that exists. The configurator reads these same names, so
# a new provider appears in the menu without the menu being told about it.
readonly SUPPORTED_BOOTLOADERS=(limine)
readonly SUPPORTED_COMPOSITORS=(niri)
readonly SUPPORTED_SHELLS=(dank)

#: Phases a bootloader must implement.
readonly BOOTLOADER_PHASES=(packages install verify)
#: Phases a desktop session must implement.
readonly DESKTOP_PHASES=(packages configure_system configure_user verify_system verify_user)

provider_function() {
    printf '%s_%s_%s' "$1" "$2" "$3"
}

provider_exists() {
    local kind="$1"
    local name="$2"
    shift 2
    local phase
    local function_name

    for phase in "$@"; do
        function_name="$(provider_function "${kind}" "${name}" "${phase}")"
        declare -F "${function_name}" >/dev/null || return 1
    done
}

# Calls the named implementation, failing with a message that says which one was
# missing rather than "command not found".
provider_call() {
    local kind="$1"
    local name="$2"
    local phase="$3"
    shift 3
    local function_name

    function_name="$(provider_function "${kind}" "${name}" "${phase}")"

    if ! declare -F "${function_name}" >/dev/null; then
        error "No ${kind} implementation named '${name}' provides ${phase}."
        error "Expected a function called ${function_name}."
        return 1
    fi

    "${function_name}" "$@"
}

provider_is_supported() {
    local candidate="$1"
    shift
    local name

    for name in "$@"; do
        [[ "${name}" == "${candidate}" ]] && return 0
    done
    return 1
}

# ------------------------------------------------------------------------------
# Bootloader
# ------------------------------------------------------------------------------

bootloader_packages() { provider_call bootloader "${BOOTLOADER}" packages; }
bootloader_install() { provider_call bootloader "${BOOTLOADER}" install; }
bootloader_verify() { provider_call bootloader "${BOOTLOADER}" verify; }

bootloader_display_name() {
    printf '%s bootloader' "${BOOTLOADER^}"
}

validate_bootloader_provider() {
    if ! provider_is_supported "${BOOTLOADER}" "${SUPPORTED_BOOTLOADERS[@]}"; then
        error "Unsupported BOOTLOADER: ${BOOTLOADER}"
        error "Available: ${SUPPORTED_BOOTLOADERS[*]}"
        return 1
    fi

    if ! provider_exists bootloader "${BOOTLOADER}" "${BOOTLOADER_PHASES[@]}"; then
        error "The '${BOOTLOADER}' bootloader is listed but not fully implemented."
        error "It must provide: ${BOOTLOADER_PHASES[*]}"
        return 1
    fi
}

# ------------------------------------------------------------------------------
# Desktop session
# ------------------------------------------------------------------------------

desktop_packages() { provider_call desktop "${DESKTOP_COMPOSITOR}" packages; }
desktop_configure_system() { provider_call desktop "${DESKTOP_COMPOSITOR}" configure_system; }
desktop_configure_user() { provider_call desktop "${DESKTOP_COMPOSITOR}" configure_user; }
desktop_verify_system() { provider_call desktop "${DESKTOP_COMPOSITOR}" verify_system; }
desktop_verify_user() { provider_call desktop "${DESKTOP_COMPOSITOR}" verify_user; }

validate_desktop_provider() {
    if ! provider_is_supported "${DESKTOP_COMPOSITOR}" "${SUPPORTED_COMPOSITORS[@]}"; then
        error "Unsupported DESKTOP_COMPOSITOR: ${DESKTOP_COMPOSITOR}"
        error "Available: ${SUPPORTED_COMPOSITORS[*]}"
        return 1
    fi

    if ! provider_is_supported "${DESKTOP_SHELL}" "${SUPPORTED_SHELLS[@]}"; then
        error "Unsupported DESKTOP_SHELL: ${DESKTOP_SHELL}"
        error "Available: ${SUPPORTED_SHELLS[*]}"
        return 1
    fi

    if ! provider_exists desktop "${DESKTOP_COMPOSITOR}" "${DESKTOP_PHASES[@]}"; then
        error "The '${DESKTOP_COMPOSITOR}' session is listed but not fully implemented."
        error "It must provide: ${DESKTOP_PHASES[*]}"
        return 1
    fi
}
