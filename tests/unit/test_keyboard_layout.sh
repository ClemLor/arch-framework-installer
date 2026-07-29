#!/usr/bin/env bash
set -Eeuo pipefail

# XKB_LAYOUT and XKB_VARIANT were validated by validate_config but never used by
# anything, so the graphical session ran on US QWERTY while the console keymap was
# correct. These tests cover the two places the layout now reaches.

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
readonly ROOT

MOUNT_ROOT="/target"
DRY_RUN="false"
USERNAME="reaper"
XKB_LAYOUT="ch"
XKB_VARIANT="fr_nodeadkeys"
KEYMAP="fr_CH"

info() { :; }
error() { :; }
success() { :; }
run_command() { :; }

# shellcheck source=lib/desktop.sh
source "${ROOT}/lib/desktop.sh"

# -- the niri configuration ----------------------------------------------------

# Niri reads its own configuration rather than /etc/X11, so the layout has to be
# injected into config.kdl.
asset="$(<"${ROOT}/assets/niri/config.kdl")"
[[ "${asset}" != *'xkb {'* ]]
printf '%s\n' 'ok - the shipped asset carries no layout of its own'

result="$(desktop_niri_apply_keyboard "${asset}")"
[[ "${result}" == *'xkb {'* ]]
[[ "${result}" == *'layout "ch"'* ]]
[[ "${result}" == *'variant "fr_nodeadkeys"'* ]]
printf '%s\n' 'ok - the layout is injected into the niri configuration'

# It has to land inside the keyboard block, not merely somewhere in the file.
inside="$(printf '%s' "${result}" | awk '
    /^[[:space:]]*keyboard[[:space:]]*\{/ { depth = 1; next }
    depth == 1 && /^[[:space:]]*\}/ { depth = 0 }
    depth == 1 { print }
')"
[[ "${inside}" == *'xkb {'* ]]
printf '%s\n' 'ok - the block is nested inside keyboard'

# Everything the asset already said must survive.
[[ "${result}" == *'numlock'* ]]
[[ "${result}" == *'natural-scroll'* ]]
printf '%s\n' 'ok - the rest of the configuration is preserved'

# Command substitution strips the block's trailing newline, so an inserted block
# printed without one leaves `}        numlock` on a single line.
grep -Eq '^[[:space:]]*numlock[[:space:]]*$' <<<"${result}"
! grep -q '}[[:space:]]*numlock' <<<"${result}"
printf '%s\n' 'ok - the following line is not glued onto the closing brace'

# Braces must still balance, or niri rejects the file outright.
opens="$(grep -o '{' <<<"${result}" | wc -l)"
closes="$(grep -o '}' <<<"${result}" | wc -l)"
[[ "${opens}" -eq "${closes}" ]]
printf '%s\n' 'ok - braces balance'

# Running twice must not stack two blocks; the configuration is rewritten on
# every install.
twice="$(desktop_niri_apply_keyboard "${result}")"
[[ "$(grep -c 'xkb {' <<<"${twice}")" -eq 1 ]]
printf '%s\n' 'ok - applying it twice does not duplicate the block'

# A layout with no variant must not emit an empty variant line, which niri
# rejects.
XKB_VARIANT=""
novariant="$(desktop_niri_apply_keyboard "${asset}")"
[[ "${novariant}" == *'layout "ch"'* ]]
[[ "${novariant}" != *'variant'* ]]
printf '%s\n' 'ok - an empty variant is omitted rather than written blank'

# -- the X11 configuration -----------------------------------------------------

# shellcheck source=lib/system.sh
source "${ROOT}/lib/system.sh"

XKB_VARIANT="fr_nodeadkeys"
x11="$(x11_keyboard_configuration)"
[[ "${x11}" == *'"XkbLayout" "ch"'* ]]
[[ "${x11}" == *'"XkbVariant" "fr_nodeadkeys"'* ]]
[[ "${x11}" == *'MatchIsKeyboard "on"'* ]]
printf '%s\n' 'ok - the X11 keyboard configuration is written from the same values'

XKB_VARIANT=""
x11="$(x11_keyboard_configuration)"
[[ "${x11}" != *'XkbVariant'* ]]
printf '%s\n' 'ok - no empty XkbVariant option'

# -- the console and graphical names differ ------------------------------------

# The whole reason both exist: fr_CH is not a valid xkb layout, and ch is not a
# valid console keymap. One value could not serve both.
[[ "${KEYMAP}" != "${XKB_LAYOUT}" ]]
printf '%s\n' 'ok - console and graphical names are genuinely different'
