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

# shellcheck source=lib/desktop.sh
source "${ROOT}/lib/desktop.sh"

configure_graphical_session
[[ "${WRITES}" == *'PATH:/etc/greetd/config.toml'* ]]
[[ "${WRITES}" == *'[initial_session]'* ]]
[[ "${WRITES}" == *'command = "niri-session"'* ]]
[[ "${WRITES}" == *'user = "alice"'* ]]
[[ "${WRITES}" == *'command = "dms-greeter --command niri -p /usr/share/quickshell/dms"'* ]]
[[ "${COMMANDS}" == *'install -Dm0755 /usr/share/quickshell/dms/Modules/Greetd/assets/dms-greeter /usr/local/bin/dms-greeter'* ]]
[[ "${COMMANDS}" == *'install -d -m0755 -o greeter -g greeter /var/cache/dms-greeter'* ]]
[[ "${COMMANDS}" == *'systemctl enable greetd.service'* ]]
[[ "${COMMANDS}" == *'systemctl set-default graphical.target'* ]]
printf '%s\n' 'ok - greetd auto-login starts niri-session with the DMS greeter as fallback'

WRITES=''
COMMANDS=''
configure_user_desktop
[[ "${COMMANDS}" == *'test -f /usr/lib/systemd/user/dms.service'* ]]
[[ "${COMMANDS}" == *'ln -sfn /usr/lib/systemd/user/dms.service /home/alice/.config/systemd/user/niri.service.wants/dms.service'* ]]
[[ "${WRITES}" == *'PATH:/home/alice/.local/bin/lock-dms-session'* ]]
[[ "${WRITES}" == *'dms ipc call lock lock'* ]]
[[ "${WRITES}" == *'niri msg action quit --skip-confirmation'* ]]
[[ "${WRITES}" == *'PATH:/home/alice/.config/systemd/user/dms-lock-on-start.service'* ]]
[[ "${WRITES}" == *'After=dms.service'* ]]
[[ "${COMMANDS}" == *'ln -sfn ../dms-lock-on-start.service /home/alice/.config/systemd/user/niri.service.wants/dms-lock-on-start.service'* ]]
[[ "${COMMANDS}" == *'chmod 0755 /home/alice/.local/bin/lock-dms-session'* ]]
printf '%s\n' 'ok - niri starts the official DMS service and locks fail-closed'

WRITES=''
COMMANDS=''
DMS_LOCK_ON_START="false"
configure_user_desktop
[[ "${COMMANDS}" == *'niri.service.wants/dms.service'* ]]
[[ "${WRITES}" != *'dms-lock-on-start.service'* ]]
[[ "${WRITES}" != *'dms ipc call lock lock'* ]]
printf '%s\n' 'ok - DMS remains linked to niri when startup locking is disabled'
