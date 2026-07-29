#!/usr/bin/env bash

# ==============================================================================
# Desktop session: niri, with Dank Material Shell
#
# Implements the desktop provider contract from lib/provider.sh:
#
#   desktop_niri_packages
#   desktop_niri_configure_system   greetd, tmpfiles, system-level session
#   desktop_niri_configure_user     the user's own configuration and units
#   desktop_niri_verify_system
#   desktop_niri_verify_user
#
# Replacing the compositor means adding desktop_<name>_* functions and listing
# the name in SUPPORTED_COMPOSITORS. The tasks and the readiness checks call
# through the dispatcher and do not mention niri.
# ==============================================================================

if [[ -n "${ARCH_INSTALLER_DESKTOP_LOADED:-}" ]]; then return 0; fi
readonly ARCH_INSTALLER_DESKTOP_LOADED="true"

# Declared by the provider so that swapping the compositor swaps its packages
# with it. desktop.list still holds what is shared by any graphical session.
desktop_niri_packages() {
    printf '%s\n' niri dms-shell-niri greetd
}

# The graphical keyboard layout.
#
# The console keymap (/etc/vconsole.conf) and the graphical layout use different
# naming schemes — fr_CH against ch/fr_nodeadkeys — and setting only the first
# leaves the desktop on US QWERTY. On a Swiss keyboard that is a session where
# half the punctuation is wrong, and it is not obvious that the cause is a
# missing xkb block rather than the keymap that was set correctly.
#
# Niri reads its own configuration rather than /etc/X11, so the block is injected
# into config.kdl. The asset carries `keyboard { numlock }`, and the layout is
# added inside it.
desktop_niri_keyboard_block() {
    printf '        xkb {\n'
    printf '            layout "%s"\n' "${XKB_LAYOUT}"
    if [[ -n "${XKB_VARIANT}" ]]; then
        printf '            variant "%s"\n' "${XKB_VARIANT}"
    fi
    printf '        }\n'
}

# Inserted after the `keyboard {` line so the asset stays readable and free of
# placeholder markers. Idempotent: an existing xkb block means the layout is
# already set and the configuration is returned unchanged.
desktop_niri_apply_keyboard() {
    local config="$1"

    if [[ "${config}" == *'xkb {'* ]]; then
        printf '%s' "${config}"
        return 0
    fi

    # print rather than printf: command substitution strips the block's trailing
    # newline, and without one the line that followed `keyboard {` ends up
    # appended to the closing brace.
    printf '%s' "${config}" | awk -v block="$(desktop_niri_keyboard_block)" '
        { print }
        /^[[:space:]]*keyboard[[:space:]]*\{/ && !inserted {
            print block
            inserted = 1
        }
    '
}

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

desktop_niri_configure_system() {
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

desktop_niri_configure_user() {
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
    niri_config="$(desktop_niri_apply_keyboard "${niri_config}")" || return 1

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

desktop_niri_verify_system() {
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

desktop_niri_verify_user() {
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

    # Without this the session runs on US QWERTY while the console keymap is
    # correct, which does not present as a keyboard configuration problem.
    if [[ "${DRY_RUN:-false}" != "true" ]]; then
        grep -Fq "layout \"${XKB_LAYOUT}\"" "${MOUNT_ROOT}${niri_config_path}" || {
            error "The Niri configuration does not set the keyboard layout."
            return 1
        }
    fi

    if [[ "${DMS_LOCK_ON_START}" != "true" ]]; then
        return 0
    fi

    verify_target_file "${launcher_path}" || return 1
    verify_target_file "${lock_unit_path}" || return 1
    [[ -L "${MOUNT_ROOT}${niri_wants_path}/dms-lock-on-start.service" ]] || return 1
    grep -Fq 'dms ipc call lock lock' "${MOUNT_ROOT}${launcher_path}"
}
