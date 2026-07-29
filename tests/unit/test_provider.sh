#!/usr/bin/env bash
set -Eeuo pipefail

# Bootloader and desktop are chosen by name and dispatched, so replacing either
# does not mean editing the tasks, the readiness checks or the package collection.
# These tests pin that: a fake provider is registered and driven end to end
# without touching anything but its own functions.

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
readonly ROOT

# shellcheck source=lib/logging.sh
source "${ROOT}/lib/logging.sh"
# shellcheck source=lib/provider.sh
source "${ROOT}/lib/provider.sh"
# shellcheck source=lib/bootloader.sh
source "${ROOT}/lib/bootloader.sh"
# shellcheck source=lib/desktop.sh
source "${ROOT}/lib/desktop.sh"

# -- the shipped providers satisfy their contracts -----------------------------

provider_exists bootloader limine "${BOOTLOADER_PHASES[@]}"
printf '%s\n' 'ok - limine implements every bootloader phase'

provider_exists desktop niri "${DESKTOP_PHASES[@]}"
printf '%s\n' 'ok - niri implements every desktop phase'

# Anything listed as supported must actually exist, or the menu would offer a
# choice that fails at install time.
for name in "${SUPPORTED_BOOTLOADERS[@]}"; do
    provider_exists bootloader "${name}" "${BOOTLOADER_PHASES[@]}" || {
        printf 'not ok - bootloader %s is listed but not implemented\n' "${name}" >&2
        exit 1
    }
done
for name in "${SUPPORTED_COMPOSITORS[@]}"; do
    provider_exists desktop "${name}" "${DESKTOP_PHASES[@]}" || {
        printf 'not ok - compositor %s is listed but not implemented\n' "${name}" >&2
        exit 1
    }
done
printf '%s\n' 'ok - every supported name is backed by an implementation'

# -- validation ----------------------------------------------------------------

BOOTLOADER="limine"
DESKTOP_COMPOSITOR="niri"
DESKTOP_SHELL="dank"
validate_bootloader_provider >/dev/null
validate_desktop_provider >/dev/null
printf '%s\n' 'ok - the shipped configuration validates'

BOOTLOADER="grub"
if validate_bootloader_provider >/dev/null 2>&1; then
    printf '%s\n' 'not ok - an unimplemented bootloader was accepted' >&2
    exit 1
fi
printf '%s\n' 'ok - an unimplemented bootloader is refused by name'

# Listed but not implemented is a distinct failure, and worth its own message:
# it means someone added a name and forgot the code.
SUPPORTED_BOOTLOADERS_BACKUP=("${SUPPORTED_BOOTLOADERS[@]}")
BOOTLOADER="halfdone"
provider_is_supported halfdone halfdone limine
bootloader_halfdone_packages() { :; }
# install and verify deliberately absent.
if provider_exists bootloader halfdone "${BOOTLOADER_PHASES[@]}"; then
    printf '%s\n' 'not ok - a partial implementation passed the contract check' >&2
    exit 1
fi
printf '%s\n' 'ok - a partial implementation is detected'

# -- dispatch ------------------------------------------------------------------

# A complete fake provider, added without editing any dispatcher. This is the
# property the whole arrangement exists for.
bootloader_fake_packages() { printf '%s\n' fake-boot; }
bootloader_fake_install() { printf 'installed\n'; }
bootloader_fake_verify() { printf 'verified\n'; }

BOOTLOADER="fake"
provider_exists bootloader fake "${BOOTLOADER_PHASES[@]}"
[[ "$(bootloader_packages)" == "fake-boot" ]]
[[ "$(bootloader_install)" == "installed" ]]
[[ "$(bootloader_verify)" == "verified" ]]
printf '%s\n' 'ok - a new bootloader works through the dispatcher alone'

[[ "$(bootloader_display_name)" == "Fake bootloader" ]]
printf '%s\n' 'ok - the task name follows the chosen implementation'

# A missing phase must say which function was expected, not "command not found".
BOOTLOADER="fake"
unset -f bootloader_fake_verify
if bootloader_verify >/dev/null 2>&1; then
    printf '%s\n' 'not ok - dispatching to a missing phase succeeded' >&2
    exit 1
fi
message="$(bootloader_verify 2>&1 || true)"
[[ "${message}" == *'bootloader_fake_verify'* ]]
printf '%s\n' 'ok - a missing phase names the function it expected'

# -- provider packages reach the package set -----------------------------------

# shellcheck source=lib/common.sh
source "${ROOT}/lib/common.sh"
# shellcheck source=lib/commands.sh
source "${ROOT}/lib/commands.sh"
# shellcheck source=lib/pacstraps.sh
source "${ROOT}/lib/pacstraps.sh"

BOOTLOADER="limine"
DESKTOP_COMPOSITOR="niri"

# Declared by the providers rather than in a list, so swapping one swaps its
# packages instead of leaving the previous one's behind.
collect_packages | grep -Fxq limine
collect_packages | grep -Fxq niri
printf '%s\n' 'ok - provider packages are part of the package set'

# -- group selection -----------------------------------------------------------

unset PACKAGE_GROUPS
[[ "$(selected_package_groups | wc -l)" -eq "${#AVAILABLE_PACKAGE_GROUPS[@]}" ]]
printf '%s\n' 'ok - an unset selection installs every group'

PACKAGE_GROUPS=(desktop)
groups="$(selected_package_groups)"
# base, firmware and framework are added back rather than rejected: a
# configuration that omits them is a mistake worth correcting, not worth aborting.
for required in base firmware framework desktop; do
    grep -Fxq "${required}" <<<"${groups}" || {
        printf 'not ok - %s missing from the selection\n' "${required}" >&2
        exit 1
    }
done
grep -Fxq multimedia <<<"${groups}" && {
    printf '%s\n' 'not ok - an unselected group was installed' >&2
    exit 1
}
printf '%s\n' 'ok - a partial selection keeps the mandatory groups'
