#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
readonly ROOT

MOUNT_ROOT="/target"
USERNAME="alice"
DESKTOP_AUTOLOGIN="true"
DMS_LOCK_ON_START="true"
DRY_RUN="false"
WRITES=''
COMMANDS=''

write_target_file() {
    WRITES+="PATH:$1
$2
"
}

run_in_chroot() {
    COMMANDS+="$*
"
}

verify_target_file() { return 0; }
project_root() { printf '%s' "${ROOT}"; }

# shellcheck source=lib/desktop.sh
source "${ROOT}/lib/desktop.sh"

configure_graphical_session
[[ "${COMMANDS}" == *'test -x /usr/share/quickshell/dms/Modules/Greetd/assets/dms-greeter'* ]]
[[ "${WRITES}" == *'PATH:/etc/greetd/config.toml'* ]]
[[ "${WRITES}" == *'[initial_session]'* ]]
[[ "${WRITES}" == *'command = "niri-session"'* ]]
[[ "${WRITES}" == *'user = "alice"'* ]]
[[ "${WRITES}" == *'command = "/usr/share/quickshell/dms/Modules/Greetd/assets/dms-greeter --command niri -p /usr/share/quickshell/dms"'* ]]
[[ "${WRITES}" == *'PATH:/etc/tmpfiles.d/dms-greeter.conf'* ]]
[[ "${WRITES}" == *'d /var/cache/dms-greeter 0750 greeter greeter -'* ]]
[[ "${WRITES}" == *'d /var/lib/greeter 0755 greeter greeter -'* ]]
[[ "${COMMANDS}" == *'systemd-tmpfiles --create /etc/tmpfiles.d/dms-greeter.conf'* ]]
[[ "${COMMANDS}" == *'systemctl enable greetd.service'* ]]
[[ "${COMMANDS}" == *'systemctl set-default graphical.target'* ]]
printf '%s\n' 'ok - greetd auto-login starts niri-session with the DMS greeter as fallback'

WRITES=''
COMMANDS=''
configure_user_desktop
[[ "${COMMANDS}" == *'test -f /usr/lib/systemd/user/dms.service'* ]]
[[ "${WRITES}" == *'PATH:/home/alice/.config/niri/config.kdl'* ]]
[[ "${WRITES}" == *'XDG_CURRENT_DESKTOP "niri"'* ]]
[[ "${WRITES}" == *'PATH:/home/alice/.config/systemd/user/niri.service.d/dms.conf'* ]]
[[ "${WRITES}" == *'Wants=dms.service'* ]]
[[ "${COMMANDS}" == *'niri validate --config /home/alice/.config/niri/config.kdl'* ]]
[[ "${WRITES}" == *'PATH:/home/alice/.local/bin/lock-dms-session'* ]]
[[ "${WRITES}" == *'dms ipc call lock lock'* ]]
[[ "${WRITES}" == *'while (( attempt < 600 ))'* ]]
[[ "${WRITES}" == *'DMS lock did not become ready within 60 seconds'* ]]
[[ "${WRITES}" == *'niri msg action quit --skip-confirmation'* ]]
[[ "${WRITES}" == *'PATH:/home/alice/.config/systemd/user/dms-lock-on-start.service'* ]]
[[ "${WRITES}" == *'After=dms.service'* ]]
[[ "${WRITES}" == *'Requires=dms.service'* ]]
[[ "${COMMANDS}" == *'ln -sfn ../dms-lock-on-start.service /home/alice/.config/systemd/user/niri.service.wants/dms-lock-on-start.service'* ]]
[[ "${COMMANDS}" == *'chmod 0755 /home/alice/.local/bin/lock-dms-session'* ]]
printf '%s\n' 'ok - niri starts the official DMS service and locks fail-closed'

WRITES=''
COMMANDS=''
DMS_LOCK_ON_START="false"
configure_user_desktop
[[ "${WRITES}" == *'niri.service.d/dms.conf'* ]]
[[ "${WRITES}" != *'dms-lock-on-start.service'* ]]
[[ "${WRITES}" != *'dms ipc call lock lock'* ]]
printf '%s\n' 'ok - DMS remains attached to niri when startup locking is disabled'
