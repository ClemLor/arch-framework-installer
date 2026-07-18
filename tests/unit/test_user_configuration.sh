#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
readonly ROOT

MOUNT_ROOT="/target"
USERNAME="alice"
USER_GROUPS="wheel,audio"
USER_SHELL="/usr/bin/fish"
DRY_RUN="true"
CALLS=''

run_in_chroot() { CALLS+="chroot:$*\n"; }
run_command() { CALLS+="command:$*\n"; }
write_target_file() { CALLS+="write:$1:$2\n"; }
info() { :; }
log_message() { :; }

# shellcheck source=lib/users.sh
source "${ROOT}/lib/users.sh"

create_installed_user
[[ "${CALLS}" == *'chroot:useradd --create-home --groups wheel,audio --shell /usr/bin/fish alice'* ]]
[[ "${CALLS}" == *'command:arch-chroot /target passwd alice'* ]]
[[ "${CALLS}" == *'command:chmod 0440 /target/etc/sudoers.d/10-wheel'* ]]
printf '%s\n' 'ok - dry-run renders user creation and password setup'

DRY_RUN="false"
CALLS=''
run_in_chroot() {
    CALLS+="chroot:$*\n"
    [[ "$1" == "id" ]] && return 0
    return 0
}
create_installed_user
[[ "${CALLS}" == *'chroot:usermod --groups wheel,audio --shell /usr/bin/fish alice'* ]]
[[ "${CALLS}" != *'useradd'* ]]
[[ "${CALLS}" != *'passwd alice'* ]]
[[ "${CALLS}" == *'chroot:visudo -cf /etc/sudoers.d/10-wheel'* ]]
printf '%s\n' 'ok - an existing account is updated without resetting its password'
