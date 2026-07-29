#!/usr/bin/env bash
set -Eeuo pipefail

TARGET_USERNAME=""
ENCRYPTION_PROFILE=""
TPM2_PROFILE=""
ZRAM_PROFILE=""
HIBERNATION_PROFILE=""
FAILURES=0

usage() {
    cat <<'EOF'
Usage: sudo ./tests/vm/validate_installation.sh \
  --user USER --encryption enabled|disabled \
  --tpm2 enabled|disabled --zram enabled|disabled \
  --hibernation enabled|disabled

Run this read-only smoke test after rebooting the installed VM.
EOF
}

parse_arguments() {
    while (( $# > 0 )); do
        case "$1" in
            --user)
                [[ $# -ge 2 ]] || return 1
                TARGET_USERNAME="$2"
                shift 2
                ;;
            --encryption)
                [[ $# -ge 2 ]] || return 1
                ENCRYPTION_PROFILE="$2"
                shift 2
                ;;
            --tpm2)
                [[ $# -ge 2 ]] || return 1
                TPM2_PROFILE="$2"
                shift 2
                ;;
            --zram)
                [[ $# -ge 2 ]] || return 1
                ZRAM_PROFILE="$2"
                shift 2
                ;;
            --hibernation)
                [[ $# -ge 2 ]] || return 1
                HIBERNATION_PROFILE="$2"
                shift 2
                ;;
            --help)
                usage
                exit 0
                ;;
            *)
                printf 'Unknown argument: %s\n' "$1" >&2
                return 1
                ;;
        esac
    done
}

validate_arguments() {
    [[ "${EUID}" -eq 0 ]] || { printf 'This validation must run as root.\n' >&2; return 1; }
    [[ "${TARGET_USERNAME}" =~ ^[a-z_][a-z0-9_-]*$ ]] || return 1
    [[ "${ENCRYPTION_PROFILE}" == "enabled" || "${ENCRYPTION_PROFILE}" == "disabled" ]] || return 1
    [[ "${TPM2_PROFILE}" == "enabled" || "${TPM2_PROFILE}" == "disabled" ]] || return 1
    [[ "${ZRAM_PROFILE}" == "enabled" || "${ZRAM_PROFILE}" == "disabled" ]] || return 1
    [[ "${HIBERNATION_PROFILE}" == "enabled" || "${HIBERNATION_PROFILE}" == "disabled" ]] || return 1
    [[ "${ENCRYPTION_PROFILE}" == "enabled" || "${TPM2_PROFILE}" == "disabled" ]] || {
        printf 'TPM2 cannot be enabled when encryption is disabled.\n' >&2
        return 1
    }
}

record_check() {
    local description="$1"
    shift

    if "$@" >/dev/null 2>&1; then
        printf '[OK] %s\n' "${description}"
    else
        printf '[FAIL] %s\n' "${description}" >&2
        ((FAILURES += 1))
    fi
}

require_validation_commands() {
    local command_name
    # Only list tools required to run the validator itself. Desktop programs
    # such as niri are part of the installation under test and must produce a
    # failed check without aborting the remaining diagnostics.
    for command_name in btrfs cmp cryptsetup find findmnt grep id jq lsattr lsblk pacman pgrep runuser snapper swapon systemctl; do
        command -v "${command_name}" >/dev/null || {
            printf 'Missing validation command: %s\n' "${command_name}" >&2
            return 1
        }
    done
}

graphics_render_node_available() {
    find /dev/dri -maxdepth 1 -type c -name 'renderD*' -print -quit 2>/dev/null |
        grep -q .
}

root_mount_is_expected_btrfs() {
    findmnt --json --mountpoint / --output FSTYPE,OPTIONS |
        jq --exit-status '
            .filesystems |
            any(
                .fstype == "btrfs" and
                ((.options | split(",")) | any(. == "subvol=@" or . == "subvol=/@"))
            )
        '
}

limine_artifacts_match() {
    local source_path='/usr/share/limine/BOOTX64.EFI'

    [[ -s "${source_path}" ]] || return 1
    cmp -s "${source_path}" /boot/EFI/arch-limine/BOOTX64.EFI || return 1
    cmp -s "${source_path}" /boot/EFI/BOOT/BOOTX64.EFI || return 1
    [[ -s /boot/limine.conf ]] || return 1
    [[ -s /boot/vmlinuz-linux-lts && -s /boot/initramfs-linux-lts.img ]] || return 1
    [[ -s /boot/vmlinuz-linux && -s /boot/initramfs-linux.img ]]
}

luks_device_path() {
    lsblk --json --output PATH,FSTYPE |
        jq --raw-output --exit-status \
            '[.. | objects | select(.fstype? == "crypto_LUKS") | .path][0] // empty'
}

luks_has_systemd_tpm2_token() {
    local device
    local metadata

    device="$(luks_device_path)" || return 1
    [[ -n "${device}" ]] || return 1
    metadata="$(cryptsetup luksDump --dump-json-metadata "${device}")" || return 1
    jq --exit-status 'any(.tokens[]?; .type == "systemd-tpm2")' <<<"${metadata}"
}

validate_storage_security_profile() {
    if [[ "${ENCRYPTION_PROFILE}" == "enabled" ]]; then
        [[ -b /dev/mapper/cryptroot ]] || return 1
        grep -Eq '(^|[[:space:]])rd\.luks\.name=' /proc/cmdline || return 1
        if [[ "${TPM2_PROFILE}" == "enabled" ]]; then
            luks_has_systemd_tpm2_token
        else
            ! luks_has_systemd_tpm2_token
        fi
        return
    fi

    [[ ! -e /dev/mapper/cryptroot ]] || return 1
    ! grep -Eq '(^|[[:space:]])rd\.luks\.name=' /proc/cmdline
}

validate_zram_profile() {
    local zram_active="false"

    if swapon --show --json |
        jq --exit-status 'any(.swapdevices[]?; .name | startswith("/dev/zram"))' >/dev/null; then
        zram_active="true"
    fi
    [[ "${ZRAM_PROFILE}" == "enabled" && "${zram_active}" == "true" ]] ||
        [[ "${ZRAM_PROFILE}" == "disabled" && "${zram_active}" == "false" ]]
}

# An active zram device is not the same as a used one. With the default
# swappiness of 60 — tuned for swap on a disk — the kernel reclaims page cache
# instead of paging to zram, so zram shows up in swapon and stays empty. That is
# the failure this checks for, and the reason the sysctl drop-in exists.
validate_zram_tuning() {
    local swappiness

    [[ "${ZRAM_PROFILE}" == "enabled" ]] || return 0

    swappiness="$(cat /proc/sys/vm/swappiness)" || return 1
    (( swappiness >= 100 )) || {
        printf 'vm.swappiness is %s; zram will be largely unused.\n' \
            "${swappiness}" >&2
        return 1
    }

    [[ "$(cat /proc/sys/vm/page-cluster)" == "0" ]]
}

# zram must outrank the swapfile. At equal priority the kernel stripes across
# both, which puts hot pages on disk and leaves the swapfile too fragmented to be
# reserved for a hibernation image.
validate_swap_priorities() {
    local zram_priority
    local file_priority

    swapon --show --json >/dev/null || return 1

    zram_priority="$(swapon --show --json |
        jq -r 'first(.swapdevices[]? | select(.name | startswith("/dev/zram")) | .prio) // empty')"
    file_priority="$(swapon --show --json |
        jq -r 'first(.swapdevices[]? | select(.type == "file") | .prio) // empty')"

    # Nothing to compare unless both exist.
    [[ -n "${zram_priority}" ]] || return 0
    [[ -n "${file_priority}" ]] || return 0

    (( zram_priority > file_priority ))
}

# A snapper config alone does not mean rollback works.
#
# Three things have to hold together: /.snapshots must be its own subvolume (or
# the root ends up containing its own snapshots), the timers must be running, and
# the pacman hooks must exist — without those the only snapshots are hourly, and
# rolling back a bad update would undo an hour of unrelated changes too.
validate_snapshot_profile() {
    findmnt --mountpoint /.snapshots >/dev/null || {
        printf '/.snapshots is not a separate mounted subvolume.\n' >&2
        return 1
    }

    [[ -s /etc/snapper/configs/root ]] || return 1
    systemctl is-enabled --quiet snapper-timeline.timer || return 1
    systemctl is-enabled --quiet snapper-cleanup.timer || return 1

    [[ -s /etc/snap-pac.ini ]] || {
        printf 'snap-pac is not configured; important updates would not be flagged.\n' >&2
        return 1
    }

    # The hooks are what actually run. Their absence means the package is missing
    # even though its configuration file is present.
    find /usr/share/libalpm/hooks -name '*snap-pac*' -print -quit 2>/dev/null |
        grep -q . || {
        printf 'snap-pac pacman hooks are not installed.\n' >&2
        return 1
    }

    snapper --config root list >/dev/null || {
        printf 'snapper cannot read the root configuration.\n' >&2
        return 1
    }
}

validate_hibernation_profile() {
    local offset

    if [[ "${HIBERNATION_PROFILE}" != "enabled" ]]; then
        ! grep -Eq '(^|[[:space:]])resume=' /proc/cmdline
        return
    fi

    swapon --show --json |
        jq --exit-status 'any(.swapdevices[]?; .type == "file")' >/dev/null || {
        printf 'Hibernation is expected but no file-backed swap is active.\n' >&2
        return 1
    }

    grep -Eq '(^|[[:space:]])resume=' /proc/cmdline || return 1

    # resume= without resume_offset= makes the kernel cold-boot silently, so the
    # presence of both is what actually matters.
    grep -Eq '(^|[[:space:]])resume_offset=[0-9]+' /proc/cmdline || {
        printf 'resume= is present but resume_offset= is missing or malformed.\n' >&2
        return 1
    }

    offset="$(btrfs inspect-internal map-swapfile --resume-offset /swap/swapfile)" || return 1
    grep -Eq "(^|[[:space:]])resume_offset=${offset}([[:space:]]|\$)" /proc/cmdline || {
        printf 'resume_offset does not match the current swapfile offset (%s).\n' \
            "${offset}" >&2
        return 1
    }

    # A copy-on-write swapfile corrupts.
    lsattr -d /swap/swapfile | grep -q 'C'
}

validate_user_desktop() {
    local niri_config="/home/${TARGET_USERNAME}/.config/niri/config.kdl"
    local niri_dropin="/home/${TARGET_USERNAME}/.config/systemd/user/niri.service.d/dms.conf"
    local wants_path="/home/${TARGET_USERNAME}/.config/systemd/user/niri.service.wants"
    local path

    id "${TARGET_USERNAME}" >/dev/null || return 1
    command -v niri >/dev/null || return 1
    for path in \
        "/home/${TARGET_USERNAME}" \
        "/home/${TARGET_USERNAME}/.cache" \
        "/home/${TARGET_USERNAME}/.config" \
        "/home/${TARGET_USERNAME}/.config/systemd/user" \
        "/home/${TARGET_USERNAME}/.local" \
        "/home/${TARGET_USERNAME}/.local/bin" \
        "/home/${TARGET_USERNAME}/.local/share"; do
        runuser --user "${TARGET_USERNAME}" -- test -w "${path}" || return 1
    done
    [[ -s "${niri_config}" ]] || return 1
    [[ -s "${niri_dropin}" ]] || return 1
    runuser --user "${TARGET_USERNAME}" -- niri validate --config "${niri_config}" || return 1
    [[ -L "${wants_path}/dms-lock-on-start.service" ]] || return 1
    pgrep --uid "${TARGET_USERNAME}" --exact niri >/dev/null || return 1
    systemctl --user --machine="${TARGET_USERNAME}@.host" is-active --quiet dms.service
}

validate_packages() {
    local package
    for package in dms-shell-niri greetd jq limine niri zram-generator; do
        pacman -Q "${package}" >/dev/null || return 1
    done
}

validate_services() {
    local unit
    for unit in NetworkManager.service fstrim.timer fwupd-refresh.timer \
        greetd.service power-profiles-daemon.service snapper-cleanup.timer \
        snapper-timeline.timer; do
        systemctl is-enabled --quiet "${unit}" || return 1
    done
    systemctl is-active --quiet NetworkManager.service || return 1
    systemctl is-active --quiet greetd.service || return 1
    [[ "$(systemctl get-default)" == "graphical.target" ]]
}

main() {
    parse_arguments "$@" || { usage >&2; return 2; }
    validate_arguments || { usage >&2; return 2; }
    require_validation_commands || return 2

    record_check "system booted in UEFI mode" test -d /sys/firmware/efi
    record_check "root is the expected Btrfs subvolume" root_mount_is_expected_btrfs
    record_check "EFI system partition is mounted" findmnt --mountpoint /boot
    record_check "Limine EFI, kernels and initramfs are intact" limine_artifacts_match
    record_check "storage encryption and TPM2 match the selected profile" validate_storage_security_profile
    record_check "required desktop and recovery packages are installed" validate_packages
    record_check "a DRM render node is available to Niri" graphics_render_node_available
    record_check "system services and graphical target are ready" validate_services
    record_check "the configured user has an active Niri/DMS session" validate_user_desktop
    record_check "zram matches the selected profile" validate_zram_profile
    record_check "the kernel is tuned to actually use zram" validate_zram_tuning
    record_check "zram outranks the swapfile" validate_swap_priorities
    record_check "hibernation matches the selected profile" validate_hibernation_profile
    record_check "snapshots and rollback are usable" validate_snapshot_profile

    if (( FAILURES > 0 )); then
        printf '%d post-boot validation check(s) failed.\n' "${FAILURES}" >&2
        return 1
    fi
    printf 'All post-boot VM validation checks passed.\n'
}

if [[ "${VM_VALIDATOR_LIBRARY_ONLY:-false}" != "true" ]]; then
    main "$@"
fi
