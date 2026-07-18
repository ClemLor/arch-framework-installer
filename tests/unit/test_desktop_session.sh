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
[[ "${WRITES}" == *'PATH:/home/alice/.local/bin/start-dms-session'* ]]
[[ "${WRITES}" == *'dms run &'* ]]
[[ "${WRITES}" == *'dms ipc call lock lock'* ]]
[[ "${WRITES}" == *'niri msg action quit --skip-confirmation'* ]]
[[ "${WRITES}" == *'PATH:/home/alice/.config/autostart/dank-material-shell.desktop'* ]]
[[ "${COMMANDS}" == *'chmod 0755 /home/alice/.local/bin/start-dms-session'* ]]
printf '%s\n' 'ok - DMS starts inside Wayland and locks fail-closed'
