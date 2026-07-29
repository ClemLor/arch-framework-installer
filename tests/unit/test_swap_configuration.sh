#!/usr/bin/env bash
set -Eeuo pipefail

# validate_config used to refuse hibernation and any non-zero SWAP_SIZE outright.
# These tests pin what replaced those blocks: the combination is allowed, but only
# when it is actually coherent.

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
readonly ROOT

FIXTURE="$(mktemp -d)"
readonly FIXTURE
trap 'rm -r "${FIXTURE}"' EXIT

# Returns 0 when the configuration validates. load_config calls fatal, which
# exits, so it has to run in a subshell for the outcome to be observable.
config_is_valid() {
    (
        set +e
        # shellcheck source=lib/logging.sh
        source "${ROOT}/lib/logging.sh"
        # shellcheck source=lib/common.sh
        source "${ROOT}/lib/common.sh"
        # shellcheck source=lib/commands.sh
        source "${ROOT}/lib/commands.sh"
        # validate_config asks the providers whether the chosen bootloader and
        # desktop exist, so the dispatcher and its implementations are needed.
        # shellcheck source=lib/provider.sh
        source "${ROOT}/lib/provider.sh"
        # shellcheck source=lib/bootloader.sh
        source "${ROOT}/lib/bootloader.sh"
        # shellcheck source=lib/desktop.sh
        source "${ROOT}/lib/desktop.sh"
        # shellcheck source=lib/config.sh
        source "${ROOT}/lib/config.sh"
        # /usr/share/zoneinfo does not exist on every development host and is
        # unrelated to what these tests cover.
        validate_timezone() { return 0; }
        CONFIG_FILE="$1" load_config
    ) >"${FIXTURE}/out.txt" 2>&1
}

reason() { grep -o 'ERROR.*' "${FIXTURE}/out.txt" | head -1; }

write_config() {
    local path="$1"
    local swap="$2"
    local hibernate="$3"
    local include_swap_subvolume="$4"

    sed \
        -e "s/^SWAP_SIZE=.*/SWAP_SIZE=\"${swap}\"/" \
        -e "s/^HIBERNATION_ENABLED=.*/HIBERNATION_ENABLED=\"${hibernate}\"/" \
        "${ROOT}/config/system.conf" >"${path}"

    if [[ "${include_swap_subvolume}" == "true" ]]; then
        sed -i 's/^    "@log"$/    "@log"\n    "@swap"/' "${path}"
    fi
}

# The shipped default: zram only, no swapfile, no hibernation. This is the path
# that already boots, so it must keep validating.
write_config "${FIXTURE}/zram-only.conf" "0GiB" "false" "false"
config_is_valid "${FIXTURE}/zram-only.conf"
printf '%s\n' 'ok - the zram-only default still validates'

write_config "${FIXTURE}/hibernate.conf" "32GiB" "true" "true"
config_is_valid "${FIXTURE}/hibernate.conf"
printf '%s\n' 'ok - hibernation with a swapfile and @swap validates'

# A swapfile without @swap would land on a copy-on-write subvolume and corrupt.
write_config "${FIXTURE}/no-subvolume.conf" "32GiB" "true" "false"
if config_is_valid "${FIXTURE}/no-subvolume.conf"; then
    printf '%s\n' 'not ok - a swapfile without the @swap subvolume was accepted' >&2
    exit 1
fi
[[ "$(reason)" == *'@swap'* ]]
printf '%s\n' 'ok - a swapfile without @swap is refused'

# zram cannot hold a hibernation image; it disappears when power is cut.
write_config "${FIXTURE}/no-swap.conf" "0GiB" "true" "false"
if config_is_valid "${FIXTURE}/no-swap.conf"; then
    printf '%s\n' 'not ok - hibernation with zero swap was accepted' >&2
    exit 1
fi
[[ "$(reason)" == *'SWAP_SIZE'* ]]
printf '%s\n' 'ok - hibernation with zero swap is refused'

# A swapfile without hibernation is legitimate: extra overflow beyond zram.
write_config "${FIXTURE}/swap-no-hibernate.conf" "8GiB" "false" "true"
config_is_valid "${FIXTURE}/swap-no-hibernate.conf"
printf '%s\n' 'ok - a swapfile without hibernation is allowed'

# @swap is not demanded when there is no swapfile to put on it.
write_config "${FIXTURE}/zram-with-subvolume.conf" "0GiB" "false" "false"
config_is_valid "${FIXTURE}/zram-with-subvolume.conf"
printf '%s\n' 'ok - @swap is not required without a swapfile'
