#!/usr/bin/env bash
set -Eeuo pipefail

# Snapper was configured but nothing ever took a snapshot except the hourly
# timeline, so the documented "roll back a bad update" story did not exist. These
# tests cover the configuration that makes it work.

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
readonly ROOT

MOUNT_ROOT="/target"
DRY_RUN="true"
WRITES=''
COMMANDS=''

write_target_file() {
    WRITES+="PATH:$1
$2
"
}

run_command() {
    COMMANDS+="$*
"
}

info() { :; }
error() { :; }
success() { :; }

# shellcheck source=lib/snapshots.sh
source "${ROOT}/lib/snapshots.sh"

configure_snapper

# -- snapper profile -----------------------------------------------------------

[[ "${WRITES}" == *'PATH:/etc/snapper/configs/root'* ]]
[[ "${WRITES}" == *'SUBVOLUME="/"'* ]]
[[ "${WRITES}" == *'PATH:/etc/conf.d/snapper'* ]]
[[ "${WRITES}" == *'SNAPPER_CONFIGS="root"'* ]]
printf '%s\n' 'ok - the Snapper root profile is written'

# Cleanup must be bounded or snapshots fill the filesystem, and a full Btrfs is
# considerably harder to recover from than a broken update.
[[ "${WRITES}" == *'TIMELINE_CLEANUP="yes"'* ]]
[[ "${WRITES}" == *'NUMBER_CLEANUP="yes"'* ]]
[[ "${WRITES}" == *'NUMBER_LIMIT="20"'* ]]
printf '%s\n' 'ok - snapshot retention is bounded'

# -- pacman hooks --------------------------------------------------------------

# The documented path is .ini, not .conf, and the values are Python literals.
# A file at the wrong path is silently ignored, which looks identical to working.
[[ "${WRITES}" == *'PATH:/etc/snap-pac.ini'* ]]
[[ "${WRITES}" != *'snap-pac.conf'* ]]
[[ "${WRITES}" == *'snapshot = True'* ]]
printf '%s\n' 'ok - snap-pac is configured at the documented path'

# NUMBER_LIMIT_IMPORTANT retains nothing unless something is flagged important.
[[ "${WRITES}" == *'important_packages'* ]]
[[ "${WRITES}" == *'important_commands'* ]]
printf '%s\n' 'ok - kernel and full-upgrade transactions are marked important'

# cleanup_algorithm is not a snap-pac key; it belongs to snapper.
[[ "${WRITES}" != *'cleanup_algorithm'* ]]
printf '%s\n' 'ok - no invalid snap-pac keys are written'

# Otherwise every no-op transaction leaves a useless pair behind.
[[ "${WRITES}" == *'EMPTY_PRE_POST_CLEANUP="yes"'* ]]
printf '%s\n' 'ok - empty pre/post pairs are cleaned up'

# -- permissions ---------------------------------------------------------------

# A snapshot contains whatever the root filesystem contained, so the directory
# listing them must not be world-readable. Skipped in dry-run, hence the second
# pass below.
[[ -z "${COMMANDS}" ]]
printf '%s\n' 'ok - dry-run runs no commands'

DRY_RUN="false"
COMMANDS=''
secure_snapshots_directory
[[ "${COMMANDS}" == *'chmod 750 /target/.snapshots'* ]]
printf '%s\n' 'ok - the snapshots directory is not world-readable'

# -- verification --------------------------------------------------------------

DRY_RUN="true"
verify_snapshot_configuration
printf '%s\n' 'ok - verification is skipped in dry-run'

DRY_RUN="false"
FIXTURE="$(mktemp -d)"
readonly FIXTURE
trap 'rm -r "${FIXTURE}"' EXIT
MOUNT_ROOT="${FIXTURE}"

verify_target_file() { [[ -s "${MOUNT_ROOT}$1" ]]; }
findmnt() { return "${FINDMNT_STATUS:-0}"; }

mkdir -p \
    "${MOUNT_ROOT}/etc/snapper/configs" \
    "${MOUNT_ROOT}/.snapshots" \
    "${MOUNT_ROOT}/usr/share/libalpm/hooks"
printf 'SUBVOLUME="/"\n' >"${MOUNT_ROOT}/etc/snapper/configs/root"
printf '[root]\nsnapshot = True\n' >"${MOUNT_ROOT}/etc/snap-pac.ini"
printf 'x\n' >"${MOUNT_ROOT}/usr/share/libalpm/hooks/05-snap-pac-pre.hook"

FINDMNT_STATUS=0
verify_snapshot_configuration
printf '%s\n' 'ok - a complete snapshot configuration verifies'

# The configuration file is optional for snap-pac, so its presence says nothing
# about whether the package is installed. The hooks are what run.
mv "${MOUNT_ROOT}/usr/share/libalpm/hooks/05-snap-pac-pre.hook" "${FIXTURE}/hook.bak"
if verify_snapshot_configuration 2>/dev/null; then
    printf '%s\n' 'not ok - a missing snap-pac hook was accepted' >&2
    exit 1
fi
printf '%s\n' 'ok - a configuration file without the hooks is refused'
mv "${FIXTURE}/hook.bak" "${MOUNT_ROOT}/usr/share/libalpm/hooks/05-snap-pac-pre.hook"

# Snapshots landing inside the root subvolume make the root contain its own
# snapshots, which cannot be rolled back cleanly.
FINDMNT_STATUS=1
if verify_snapshot_configuration 2>/dev/null; then
    printf '%s\n' 'not ok - an unmounted /.snapshots was accepted' >&2
    exit 1
fi
printf '%s\n' 'ok - /.snapshots must be a separate mounted subvolume'

FINDMNT_STATUS=0
rm -f "${MOUNT_ROOT}/etc/snap-pac.ini"
if verify_snapshot_configuration 2>/dev/null; then
    printf '%s\n' 'not ok - a missing snap-pac configuration was accepted' >&2
    exit 1
fi
printf '%s\n' 'ok - a missing snap-pac configuration is refused'
