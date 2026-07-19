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

desktop_niri_config_path() {
    printf '/home/%s/.config/niri/config.kdl' "${USERNAME}"
}

desktop_niri_dropin_path() {
    printf '/home/%s/.config/systemd/user/niri.service.d/dms.conf' "${USERNAME}"
}

configure_graphical_session() {
    local greeter_asset='/usr/share/quickshell/dms/Modules/Greetd/assets/dms-greeter'
    local greetd_config
    local greeter_command="${greeter_asset} --command niri -p /usr/share/quickshell/dms"

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

    run_in_chroot test -x "${greeter_asset}" || return 1
    write_target_file /etc/tmpfiles.d/dms-greeter.conf 'd /var/cache/dms-greeter 0750 greeter greeter -
d /var/lib/greeter 0755 greeter greeter -
' || return 1
    run_in_chroot systemd-tmpfiles --create /etc/tmpfiles.d/dms-greeter.conf || return 1
    write_target_file /etc/greetd/config.toml "${greetd_config}" || return 1
    run_in_chroot systemctl enable greetd.service || return 1
    run_in_chroot systemctl set-default graphical.target
}

configure_user_desktop() {
    local launcher_path
    local lock_unit_path
    local niri_config
    local niri_config_path
    local niri_dropin_path
    local niri_wants_path

    launcher_path="$(desktop_lock_launcher_path)"
    lock_unit_path="$(desktop_lock_unit_path)"
    niri_config_path="$(desktop_niri_config_path)"
    niri_dropin_path="$(desktop_niri_dropin_path)"
    niri_wants_path="$(desktop_niri_wants_path)"
    niri_config="$(<"$(project_root)/assets/niri/config.kdl")" || return 1

    run_in_chroot test -f /usr/lib/systemd/user/dms.service || return 1
    run_in_chroot install -d -m0755 -o "${USERNAME}" -g "${USERNAME}" \
        "/home/${USERNAME}/.local/bin" "${niri_wants_path}" \
        "/home/${USERNAME}/.config/niri" \
        "/home/${USERNAME}/.config/systemd/user/niri.service.d" || return 1
    write_target_file "${niri_config_path}" "${niri_config}" || return 1
    write_target_file "${niri_dropin_path}" '[Unit]
Wants=dms.service
' || return 1
    run_in_chroot niri validate --config "${niri_config_path}" || return 1

    if [[ "${DMS_LOCK_ON_START}" != "true" ]]; then
        return 0
    fi

    write_target_file "${launcher_path}" '#!/usr/bin/env bash
set -u

attempt=0
while (( attempt < 600 )); do
    if dms ipc call lock lock >/dev/null 2>&1; then
        exit 0
    fi
    sleep 0.1
    ((attempt += 1))
done

# Auto-login must fail closed if the requested lock screen is unavailable.
printf '%s\n' "DMS lock did not become ready within 60 seconds; closing Niri." >&2
if niri msg action quit --skip-confirmation >/dev/null 2>&1; then
    exit 0
fi
exit 1
' || return 1

    write_target_file "${lock_unit_path}" "[Unit]
Description=Lock the auto-login Niri session with DMS
PartOf=niri.service
After=dms.service
Requires=dms.service

[Service]
Type=oneshot
ExecStart=${launcher_path}
" || return 1

    run_in_chroot ln -sfn ../dms-lock-on-start.service \
        "${niri_wants_path}/dms-lock-on-start.service" || return 1
    run_in_chroot chown "${USERNAME}:${USERNAME}" \
        "${niri_config_path}" "${niri_dropin_path}" \
        "${launcher_path}" "${lock_unit_path}" || return 1
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
    grep -Fq 'command = "/usr/share/quickshell/dms/Modules/Greetd/assets/dms-greeter --command niri -p /usr/share/quickshell/dms"' \
        "${MOUNT_ROOT}/etc/greetd/config.toml" || return 1
    verify_target_file /etc/tmpfiles.d/dms-greeter.conf || return 1
    run_in_chroot test -d /var/cache/dms-greeter || return 1
    run_in_chroot test -d /var/lib/greeter || return 1
    run_in_chroot systemctl is-enabled greetd.service >/dev/null
}

verify_user_desktop() {
    local launcher_path
    local lock_unit_path
    local niri_config_path
    local niri_dropin_path
    local niri_wants_path

    launcher_path="$(desktop_lock_launcher_path)"
    lock_unit_path="$(desktop_lock_unit_path)"
    niri_config_path="$(desktop_niri_config_path)"
    niri_dropin_path="$(desktop_niri_dropin_path)"
    niri_wants_path="$(desktop_niri_wants_path)"
    verify_target_file "${niri_config_path}" || return 1
    verify_target_file "${niri_dropin_path}" || return 1
    run_in_chroot niri validate --config "${niri_config_path}" || return 1

    if [[ "${DMS_LOCK_ON_START}" != "true" ]]; then
        return 0
    fi

    verify_target_file "${launcher_path}" || return 1
    verify_target_file "${lock_unit_path}" || return 1
    [[ -L "${MOUNT_ROOT}${niri_wants_path}/dms-lock-on-start.service" ]] || return 1
    grep -Fq 'dms ipc call lock lock' "${MOUNT_ROOT}${launcher_path}"
}
