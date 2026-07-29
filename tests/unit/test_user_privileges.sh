#!/usr/bin/env bash
set -Eeuo pipefail

# The installer never sets a root password, so root stays locked and sudo through
# wheel is the only administrative access the machine has.
#
# The sudoers drop-in granting %wheel and the account being in wheel are separate
# facts. Each looks correct alone, and only together do they grant anything — so
# a configuration that omits wheel produced a machine nobody could administer,
# with every individual check passing.

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
readonly ROOT

# shellcheck source=lib/logging.sh
source "${ROOT}/lib/logging.sh"
# shellcheck source=lib/config.sh
source "${ROOT}/lib/config.sh"

# -- configuration -------------------------------------------------------------

USERNAME="reaper"
USER_SHELL="/usr/bin/fish"

USER_GROUPS="wheel,audio,video,input,storage"
validate_identity_configuration
printf '%s\n' 'ok - a configuration including wheel is accepted'

USER_GROUPS="wheel"
validate_identity_configuration
printf '%s\n' 'ok - wheel alone is accepted'

# The failure this exists to prevent: valid format, real groups, no sudo.
USER_GROUPS="audio,video,input,storage"
if validate_identity_configuration 2>/dev/null; then
    printf '%s\n' 'not ok - a configuration without wheel was accepted' >&2
    exit 1
fi
printf '%s\n' 'ok - a configuration without wheel is refused'

# Substring matches must not count: "wheelless" is not wheel.
USER_GROUPS="wheelless,audio"
if validate_identity_configuration 2>/dev/null; then
    printf '%s\n' 'not ok - a group merely containing "wheel" was accepted' >&2
    exit 1
fi
printf '%s\n' 'ok - a group name containing wheel does not count'

USER_GROUPS="audio,wheel"
validate_identity_configuration
printf '%s\n' 'ok - wheel is found in any position'

# -- the installed system ------------------------------------------------------

MOUNT_ROOT="/target"
DRY_RUN="false"

# shellcheck source=lib/users.sh
source "${ROOT}/lib/users.sh"

CHROOT_GROUPS="reaper wheel audio video"
SUDO_PRESENT="true"
SUDO_LIST="true"
ROOT_STATUS="root P 07/29/2026 0 99999 7 -1"

run_in_chroot() {
    case "$*" in
        *"id --name --groups"*) printf '%s\n' "${CHROOT_GROUPS}" ;;
        *"command -v sudo"*) [[ "${SUDO_PRESENT}" == "true" ]] ;;
        *"sudo --list"*) [[ "${SUDO_LIST}" == "true" ]] ;;
        *"passwd --status root"*) printf '%s\n' "${ROOT_STATUS}" ;;
        *) return 0 ;;
    esac
}

verify_installed_user_privileges
printf '%s\n' 'ok - a user in wheel with sudo installed verifies'

CHROOT_GROUPS="reaper audio video"
if verify_installed_user_privileges 2>/dev/null; then
    printf '%s\n' 'not ok - a user outside wheel was accepted' >&2
    exit 1
fi
printf '%s\n' 'ok - a user outside wheel is refused'

# "wheelless" again, this time in the installed system.
CHROOT_GROUPS="reaper wheelless"
if verify_installed_user_privileges 2>/dev/null; then
    printf '%s\n' 'not ok - a group containing wheel satisfied the check' >&2
    exit 1
fi
printf '%s\n' 'ok - membership matching is exact'

# The drop-in is useless without the package, and pacstrap could have been given
# a shortened list.
CHROOT_GROUPS="reaper wheel"
SUDO_PRESENT="false"
if verify_installed_user_privileges 2>/dev/null; then
    printf '%s\n' 'not ok - a missing sudo binary was accepted' >&2
    exit 1
fi
printf '%s\n' 'ok - a missing sudo package is refused'

# Asks sudo itself rather than trusting that a valid file grants what it appears
# to grant.
SUDO_PRESENT="true"
SUDO_LIST="false"
if verify_installed_user_privileges 2>/dev/null; then
    printf '%s\n' 'not ok - sudo granting nothing was accepted' >&2
    exit 1
fi
printf '%s\n' 'ok - sudo granting no privileges is refused'

SUDO_LIST="true"
DRY_RUN="true"
verify_installed_user_privileges
printf '%s\n' 'ok - verification is skipped in dry-run'

# -- the root fallback ---------------------------------------------------------

# A locked root plus any fault in the sudo path leaves no way in at all, which on
# an encrypted disk means reinstalling.
DRY_RUN="false"

ROOT_STATUS="root P 07/29/2026 0 99999 7 -1"
root_password_is_set
verify_root_password
printf '%s\n' 'ok - a usable root password verifies'

# What a fresh pacstrap leaves behind.
ROOT_STATUS="root L 07/29/2026 0 99999 7 -1"
if root_password_is_set; then
    printf '%s\n' 'not ok - a locked root account counted as having a password' >&2
    exit 1
fi
if verify_root_password 2>/dev/null; then
    printf '%s\n' 'not ok - a locked root account was accepted' >&2
    exit 1
fi
printf '%s\n' 'ok - a locked root account is refused'

ROOT_STATUS="root NP 07/29/2026 0 99999 7 -1"
if verify_root_password 2>/dev/null; then
    printf '%s\n' 'not ok - an empty root password was accepted' >&2
    exit 1
fi
printf '%s\n' 'ok - an empty root password is refused'

DRY_RUN="true"
verify_root_password
printf '%s\n' 'ok - the root check is skipped in dry-run'

# Re-running an installation must not prompt again for a password that exists.
ROOT_STATUS="root P 07/29/2026 0 99999 7 -1"
DRY_RUN="false"
PROMPTED="false"
arch-chroot() { PROMPTED="true"; }
set_root_password >/dev/null
[[ "${PROMPTED}" == "false" ]]
printf '%s\n' 'ok - an existing root password is left alone'

# And must prompt when there is none.
ROOT_STATUS="root L 07/29/2026 0 99999 7 -1"
PROMPTED="false"
log_message() { :; }
set_root_password >/dev/null
[[ "${PROMPTED}" == "true" ]]
printf '%s\n' 'ok - a locked root account is prompted for a password'

# -- the shipped configuration -------------------------------------------------

grep -q '^sudo$' "${ROOT}/packages/base.list"
printf '%s\n' 'ok - sudo is in the base package list'

grep -qE '^USER_GROUPS=.*\bwheel\b' "${ROOT}/config/system.conf"
printf '%s\n' 'ok - the shipped configuration puts the user in wheel'
