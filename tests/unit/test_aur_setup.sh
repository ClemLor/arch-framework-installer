#!/usr/bin/env bash
set -Eeuo pipefail

# AUR packages are never passed to pacstrap. The installer writes a script and
# the user runs it after the first boot, so a broken PKGBUILD is an inconvenience
# rather than a failed installation.

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
readonly ROOT

FIXTURE="$(mktemp -d)"
readonly FIXTURE
trap 'rm -r "${FIXTURE}"' EXIT

MOUNT_ROOT="${FIXTURE}"
DRY_RUN="false"
COMMANDS=''

# Writes for real: the generated script has to be parsed as Bash below, which is
# the only way to catch a quoting mistake in a heredoc-free nested script.
write_target_file() {
    local path="${MOUNT_ROOT}$1"
    mkdir -p "$(dirname "${path}")"
    printf '%s' "$2" >"${path}"
}

run_command() {
    COMMANDS+="$*
"
    "$@"
}

project_root() { printf '%s' "${ROOT}"; }
info() { :; }
error() { :; }
success() { :; }

# shellcheck source=lib/pacstraps.sh
source "${ROOT}/lib/pacstraps.sh"
# shellcheck source=lib/aur.sh
source "${ROOT}/lib/aur.sh"

configure_aur_setup

SCRIPT="${MOUNT_ROOT}/usr/local/bin/afi-aur-setup"
LIST="${MOUNT_ROOT}/usr/local/share/arch-framework-installer/aur.list"

# -- what was written ----------------------------------------------------------

[[ -s "${SCRIPT}" ]]
[[ -x "${SCRIPT}" ]]
[[ "${COMMANDS}" == *'chmod 0755'* ]]
printf '%s\n' 'ok - the setup script is installed and executable'

# The repository is gone after a reboot, so the list must live on the target.
[[ -s "${LIST}" ]]
grep -Fq 'librewolf-bin' "${LIST}"
grep -Fq 'visual-studio-code-bin' "${LIST}"
grep -Fq 'cursor-bin' "${LIST}"
printf '%s\n' 'ok - the package list is copied into the target'

# Comments are stripped on the way in, so the script does not have to re-parse
# them and cannot mistake one for a package name.
! grep -q '^#' "${LIST}"
! grep -q '^[[:space:]]*$' "${LIST}"
printf '%s\n' 'ok - the copied list contains only package names'

# paru installs the list, so it cannot be an entry in it.
! grep -qx 'paru' "${LIST}"
printf '%s\n' 'ok - the helper is not listed among the packages it installs'

# -- the generated script ------------------------------------------------------

# A quoting error inside the nested script would only surface on the installed
# machine, after a reboot, which is the worst possible time to find it.
bash -n "${SCRIPT}"
printf '%s\n' 'ok - the generated script is valid Bash'

grep -Fq 'set -Eeuo pipefail' "${SCRIPT}"
printf '%s\n' 'ok - the generated script fails loudly'

# makepkg refuses to run as root, and building as root would leave root-owned
# files behind even if it did not.
grep -Fq 'EUID' "${SCRIPT}"
grep -Fq 'makepkg refuses to run as root' "${SCRIPT}"
printf '%s\n' 'ok - the script refuses to run as root'

# Substitutions must have been expanded, not left as literals.
grep -Fq '/usr/local/share/arch-framework-installer/aur.list' "${SCRIPT}"
grep -Fq 'https://aur.archlinux.org/paru.git' "${SCRIPT}"
! grep -q 'AUR_LIST_PATH' "${SCRIPT}"
! grep -q 'AUR_HELPER_REPOSITORY' "${SCRIPT}"
printf '%s\n' 'ok - paths and the helper repository are expanded'

# One package at a time: a single --needed invocation aborts the whole set when
# one PKGBUILD is broken, which would routinely leave most of the list uninstalled.
grep -Fq 'for package in' "${SCRIPT}"
grep -Fq 'failed+=' "${SCRIPT}"
printf '%s\n' 'ok - one failed package does not abandon the rest'

# Re-running must be safe; the machine will need it the first time a build breaks.
grep -Fq -- '--needed' "${SCRIPT}"
grep -Fq 'is already installed' "${SCRIPT}"
printf '%s\n' 'ok - the script is idempotent'

# -- verification --------------------------------------------------------------

verify_target_file() { [[ -s "${MOUNT_ROOT}$1" ]]; }
run_in_chroot() { return "${CHROOT_STATUS:-0}"; }

CHROOT_STATUS=0
verify_aur_setup
printf '%s\n' 'ok - a complete AUR setup verifies'

# Without git, base-devel and sudo the script cannot build anything, and finding
# that out after a reboot is worse than finding it out now.
CHROOT_STATUS=1
if verify_aur_setup 2>/dev/null; then
    printf '%s\n' 'not ok - missing build prerequisites were accepted' >&2
    exit 1
fi
printf '%s\n' 'ok - missing build prerequisites are refused'

CHROOT_STATUS=0
chmod -x "${SCRIPT}"
if [[ -x "${SCRIPT}" ]]; then
    # Some filesystems cannot drop the execute bit, so the condition under test
    # cannot be created here. Skipped rather than asserted falsely.
    printf '%s\n' 'skip - this filesystem does not honour chmod -x'
else
    if verify_aur_setup 2>/dev/null; then
        printf '%s\n' 'not ok - a non-executable script was accepted' >&2
        exit 1
    fi
    printf '%s\n' 'ok - a non-executable script is refused'
fi

chmod +x "${SCRIPT}"
DRY_RUN="true"
verify_aur_setup
printf '%s\n' 'ok - verification is skipped in dry-run'
