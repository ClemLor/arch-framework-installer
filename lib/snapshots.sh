#!/usr/bin/env bash

if [[ -n "${ARCH_INSTALLER_SNAPSHOTS_LOADED:-}" ]]; then return 0; fi
readonly ARCH_INSTALLER_SNAPSHOTS_LOADED="true"

configure_snapper() {
    write_target_file /etc/snapper/configs/root 'SUBVOLUME="/"
FSTYPE="btrfs"
ALLOW_USERS=""
ALLOW_GROUPS="wheel"
TIMELINE_CREATE="yes"
TIMELINE_CLEANUP="yes"
NUMBER_CLEANUP="yes"
NUMBER_MIN_AGE="1800"
NUMBER_LIMIT="50"
NUMBER_LIMIT_IMPORTANT="10"
' || return 1
    write_target_file /etc/conf.d/snapper 'SNAPPER_CONFIGS="root"
'
}
