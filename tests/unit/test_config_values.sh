#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
readonly ROOT

error() { :; }

# shellcheck source=lib/config.sh
source "${ROOT}/lib/config.sh"

ZONEINFO_ROOT="$(mktemp -d)"
trap 'rm -r "${ZONEINFO_ROOT}"' EXIT
mkdir -p "${ZONEINFO_ROOT}/Europe"
touch "${ZONEINFO_ROOT}/Europe/Zurich"

HOSTNAME="framework"
validate_hostname
HOSTNAME="invalid..host"
! validate_hostname
printf '%s\n' 'ok - hostnames are validated before installation'

TIMEZONE="Europe/Zurich"
validate_timezone
TIMEZONE="../../etc/passwd"
! validate_timezone
printf '%s\n' 'ok - timezone paths are constrained to zoneinfo'

USERNAME="reaper"
USER_SHELL="/usr/bin/fish"
USER_GROUPS="wheel,audio,video"
validate_identity_configuration
USERNAME="Invalid User"
! validate_identity_configuration
printf '%s\n' 'ok - account values are validated before installation'

LOCALE="en_US.UTF-8"
SECONDARY_LOCALE="fr_CH.UTF-8"
KEYMAP="fr_CH"
validate_locale_configuration
KEYMAP="../../bad"
! validate_locale_configuration
printf '%s\n' 'ok - locale and keymap values reject unsafe input'
