#!/usr/bin/env bash

# ==============================================================================
# Module: ui
#
# Purpose:
#   Provide reusable user interaction functions.
#
# Idempotent:
#   Yes
# ==============================================================================

if [[ -n "${ARCH_INSTALLER_UI_LOADED:-}" ]]; then
    return 0
fi

readonly ARCH_INSTALLER_UI_LOADED="true"

confirm() {
    local prompt="${1:-Continue?}"
    local answer

    if [[ "${INTERACTIVE_CONFIRMATION:-true}" != "true" ]]; then
        return 0
    fi

    read -r -p "${prompt} [y/N] " answer

    case "${answer}" in
        y | Y | yes | YES)
            return 0
            ;;
        *)
            return 1
            ;;
    esac
}

confirm_destructive_action() {
    local expected_value="$1"
    local prompt="$2"
    local answer

    printf '%s\n' "${prompt}"
    printf 'Type "%s" to continue: ' "${expected_value}"
    read -r answer

    [[ "${answer}" == "${expected_value}" ]]
}

pause() {
    if [[ "${INTERACTIVE_CONFIRMATION:-true}" == "true" ]]; then
        read -r -p "Press Enter to continue..."
    fi
}
