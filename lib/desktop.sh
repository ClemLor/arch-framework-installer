#!/usr/bin/env bash

if [[ -n "${ARCH_INSTALLER_DESKTOP_LOADED:-}" ]]; then return 0; fi
readonly ARCH_INSTALLER_DESKTOP_LOADED="true"

desktop_lock_launcher_path() {
    printf '/home/%s/.local/bin/lock-dms-session' "${USERNAME}"
}

desktop_lock_unit_path() {
    printf '/home/%s/.config/systemd/user/dms-lock-on-start.service' "${USERNAME}"
}

desktop_niri_wants_path() {
    printf '/home/%s/.config/systemd/user/niri.service.wants' "${USERNAME}"
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
    local launcher_path
    local lock_unit_path
    local niri_wants_path

    launcher_path="$(desktop_lock_launcher_path)"
    lock_unit_path="$(desktop_lock_unit_path)"
    niri_wants_path="$(desktop_niri_wants_path)"

    run_in_chroot test -f /usr/lib/systemd/user/dms.service || return 1
    run_in_chroot install -d -m0755 -o "${USERNAME}" -g "${USERNAME}" \
        "/home/${USERNAME}/.local/bin" "${niri_wants_path}" || return 1
    run_in_chroot ln -sfn /usr/lib/systemd/user/dms.service \
        "${niri_wants_path}/dms.service" || return 1

    if [[ "${DMS_LOCK_ON_START}" != "true" ]]; then
        return 0
    fi

    write_target_file "${launcher_path}" '#!/usr/bin/env bash
set -u

attempt=0
while (( attempt < 100 )); do
    if dms ipc call lock lock >/dev/null 2>&1; then
        exit 0
    fi
    sleep 0.1
    ((attempt += 1))
done

# Auto-login must fail closed if the requested lock screen is unavailable.
if niri msg action quit --skip-confirmation >/dev/null 2>&1; then
    exit 0
fi
exit 1
' || return 1

    write_target_file "${lock_unit_path}" "[Unit]
Description=Lock the auto-login Niri session with DMS
PartOf=niri.service
After=dms.service

[Service]
Type=oneshot
ExecStart=${launcher_path}
" || return 1

    run_in_chroot ln -sfn ../dms-lock-on-start.service \
        "${niri_wants_path}/dms-lock-on-start.service" || return 1
    run_in_chroot chown "${USERNAME}:${USERNAME}" "${launcher_path}" "${lock_unit_path}" || return 1
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
    local launcher_path
    local lock_unit_path
    local niri_wants_path

    launcher_path="$(desktop_lock_launcher_path)"
    lock_unit_path="$(desktop_lock_unit_path)"
    niri_wants_path="$(desktop_niri_wants_path)"
    [[ -L "${MOUNT_ROOT}${niri_wants_path}/dms.service" ]] || return 1

    if [[ "${DMS_LOCK_ON_START}" != "true" ]]; then
        return 0
    fi

    verify_target_file "${launcher_path}" || return 1
    verify_target_file "${lock_unit_path}" || return 1
    [[ -L "${MOUNT_ROOT}${niri_wants_path}/dms-lock-on-start.service" ]] || return 1
    grep -Fq 'dms ipc call lock lock' "${MOUNT_ROOT}${launcher_path}"
}
