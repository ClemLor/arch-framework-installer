#!/usr/bin/env bash

if [[ -n "${ARCH_INSTALLER_DESKTOP_LOADED:-}" ]]; then return 0; fi
readonly ARCH_INSTALLER_DESKTOP_LOADED="true"

desktop_session_launcher_path() {
    printf '/home/%s/.local/bin/start-dms-session' "${USERNAME}"
}

desktop_autostart_path() {
    printf '/home/%s/.config/autostart/dank-material-shell.desktop' "${USERNAME}"
}

configure_graphical_session() {
    local greeter_asset='/usr/share/quickshell/dms/Modules/Greetd/assets/dms-greeter'
    local greetd_config
    local greeter_command='dms-greeter --command niri -p /usr/share/quickshell/dms'

    if [[ "${DESKTOP_AUTOLOGIN}" == "true" ]]; then
        greetd_config="[terminal]
vt = 1

[initial_session]
command = \"niri-session\"
user = \"${USERNAME}\"

[default_session]
command = \"${greeter_command}\"
user = \"greeter\"
"
    else
        greetd_config="[terminal]
vt = 1

[default_session]
command = \"${greeter_command}\"
user = \"greeter\"
"
    fi

    run_in_chroot test -f "${greeter_asset}" || return 1
    run_in_chroot install -Dm0755 "${greeter_asset}" /usr/local/bin/dms-greeter || return 1
    run_in_chroot install -d -m0755 -o greeter -g greeter /var/cache/dms-greeter || return 1
    write_target_file /etc/greetd/config.toml "${greetd_config}" || return 1
    run_in_chroot systemctl enable greetd.service || return 1
    run_in_chroot systemctl set-default graphical.target
}

configure_user_desktop() {
    local autostart_path
    local launcher_path
    local lock_command=''

    launcher_path="$(desktop_session_launcher_path)"
    autostart_path="$(desktop_autostart_path)"

    if [[ "${DMS_LOCK_ON_START}" == "true" ]]; then
        lock_command='attempt=0
while (( attempt < 100 )); do
    if dms ipc call lock lock >/dev/null 2>&1; then
        wait "${dms_pid}"
        exit $?
    fi
    if ! kill -0 "${dms_pid}" 2>/dev/null; then
        wait "${dms_pid}"
        exit $?
    fi
    sleep 0.1
    ((attempt += 1))
done

# Auto-login must fail closed if the requested lock screen is unavailable.
niri msg action quit --skip-confirmation >/dev/null 2>&1 || true
wait "${dms_pid}"
'
    fi

    write_target_file "${launcher_path}" "#!/usr/bin/env bash
set -u

dms run &
dms_pid=\$!
${lock_command}
wait \"\${dms_pid}\"
" || return 1

    write_target_file "${autostart_path}" "[Desktop Entry]
Type=Application
Name=Dank Material Shell
Comment=Start DMS after the Wayland session is ready
Exec=${launcher_path}
OnlyShowIn=niri;
X-GNOME-Autostart-enabled=true
" || return 1

    run_in_chroot chown -R "${USERNAME}:${USERNAME}" "/home/${USERNAME}/.local" "/home/${USERNAME}/.config" || return 1
    run_in_chroot chmod 0755 "${launcher_path}"
}

verify_graphical_session() {
    if [[ "${DRY_RUN}" == "true" ]]; then
        return 0
    fi

    verify_target_file /etc/greetd/config.toml || return 1
    if [[ "${DESKTOP_AUTOLOGIN}" == "true" ]]; then
        grep -Fq '[initial_session]' "${MOUNT_ROOT}/etc/greetd/config.toml" || return 1
        grep -Fq 'command = "niri-session"' "${MOUNT_ROOT}/etc/greetd/config.toml" || return 1
    fi
    grep -Fq 'command = "dms-greeter --command niri -p /usr/share/quickshell/dms"' \
        "${MOUNT_ROOT}/etc/greetd/config.toml" || return 1
    verify_target_file /usr/local/bin/dms-greeter || return 1
    run_in_chroot systemctl is-enabled greetd.service >/dev/null
}

verify_user_desktop() {
    local autostart_path
    local launcher_path

    launcher_path="$(desktop_session_launcher_path)"
    autostart_path="$(desktop_autostart_path)"
    verify_target_file "${launcher_path}" || return 1
    verify_target_file "${autostart_path}" || return 1
    grep -Fq 'dms ipc call lock lock' "${MOUNT_ROOT}${launcher_path}"
}
