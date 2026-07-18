#!/usr/bin/env bash

if [[ -n "${ARCH_INSTALLER_PROGRESS_LOADED:-}" ]]; then
    return 0
fi
readonly ARCH_INSTALLER_PROGRESS_LOADED="true"

progress_start() {
    local current="$1"
    local total="$2"
    local name="$3"
    printf '[%02d/%02d] %-24s …\n' "${current}" "${total}" "${name}"
}

progress_success() {
    local current="$1"
    local total="$2"
    local name="$3"
    local duration="$4"
    printf '[%02d/%02d] %-24s ✔ (%ss)\n' "${current}" "${total}" "${name}" "${duration}"
}

progress_failure() {
    local current="$1"
    local total="$2"
    local name="$3"
    local phase="$4"
    printf '[%02d/%02d] %-24s ✘ (%s)\n' "${current}" "${total}" "${name}" "${phase}" >&2
}
