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

# P means root already has a usable password, so set_root_password leaves it
# alone. The locked case is covered in test_user_privileges.sh.
ROOT_STATUS="root P 07/29/2026 0 99999 7 -1"

run_in_chroot() {
    CALLS+="chroot:$*\n"
    [[ "$*" == *"passwd --status root"* ]] && printf '%s\n' "${ROOT_STATUS}"
    return 0
}
run_command() { CALLS+="command:$*\n"; }
write_target_file() { CALLS+="write:$1:$2\n"; }
info() { :; }
log_message() { :; }

# shellcheck source=lib/users.sh
source "${ROOT}/lib/users.sh"

create_installed_user
[[ "${CALLS}" == *'chroot:useradd --create-home --groups wheel,audio --shell /usr/bin/fish alice'* ]]
[[ "${CALLS}" == *'command:arch-chroot /target passwd alice'* ]]
[[ "${CALLS}" == *'chroot:chown alice:alice /home/alice'* ]]
[[ "${CALLS}" == *'chroot:install -d -m0700 -o alice -g alice /home/alice/.cache /home/alice/.config /home/alice/.local /home/alice/.local/share'* ]]
[[ "${CALLS}" == *'chroot:install -d -m0755 -o alice -g alice /home/alice/.config/systemd /home/alice/.config/systemd/user /home/alice/.local/bin'* ]]
[[ "${CALLS}" == *'command:chmod 0440 /target/etc/sudoers.d/10-wheel'* ]]
printf '%s\n' 'ok - dry-run renders user creation and password setup'

# Both passwords are prompted, and neither is ever written to a file.
[[ "${CALLS}" == *'command:arch-chroot /target passwd root'* ]]
[[ "${CALLS}" != *'write:'*'passwd'* ]]
printf '%s\n' 'ok - dry-run renders the root password prompt'

DRY_RUN="false"
CALLS=''
run_in_chroot() {
    CALLS+="chroot:$*\n"
    [[ "$*" == *"passwd --status root"* ]] && printf '%s\n' "${ROOT_STATUS}"
    return 0
}
create_installed_user
[[ "${CALLS}" == *'chroot:usermod --groups wheel,audio --shell /usr/bin/fish alice'* ]]
[[ "${CALLS}" != *'useradd'* ]]
[[ "${CALLS}" != *'passwd alice'* ]]
[[ "${CALLS}" == *'chroot:chown alice:alice /home/alice'* ]]
[[ "${CALLS}" == *'chroot:visudo -cf /etc/sudoers.d/10-wheel'* ]]
printf '%s\n' 'ok - an existing account is updated without resetting its password'

# Re-running an installation must not prompt for a root password that exists.
#
# The status lookup itself is invisible here: it runs inside a command
# substitution, so its own bookkeeping happens in a subshell. What is observable
# is that no password was set, which is the property that matters.
[[ "${CALLS}" != *'passwd root'* ]]
printf '%s\n' 'ok - an existing root password is not reset either'

CALLS=''
run_in_chroot() {
    CALLS+="chroot:$*\n"
    [[ "$1" != "runuser" || "$7" != "/home/alice/.local/share" ]]
}
if verify_installed_user_home >/dev/null 2>&1; then
    printf '%s\n' 'not ok - an unwritable XDG directory passed user verification' >&2
    exit 1
fi
[[ "${CALLS}" == *'runuser --user alice -- test -w /home/alice/.config'* ]]
printf '%s\n' 'ok - user verification rejects an unwritable XDG directory'
