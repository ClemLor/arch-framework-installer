#!/usr/bin/env bash
set -Eeuo pipefail

# Hibernation was previously refused outright by validate_config. These tests
# cover the pieces that make it work, and the orderings that make it work
# correctly rather than merely appear configured.

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
readonly ROOT

MOUNT_ROOT="/target"
DRY_RUN="false"
WRITES=''
COMMANDS=''

write_target_file() {
    WRITES+="PATH:$1
$2
"
}

run_command() {
    COMMANDS+="$*
"
}

info() { :; }
error() { :; }
success() { :; }
require_commands_for_mode() { return 0; }

# shellcheck source=lib/partition.sh
source "${ROOT}/lib/partition.sh"
# shellcheck source=lib/memory.sh
source "${ROOT}/lib/memory.sh"

# -- swap sizing ---------------------------------------------------------------

SWAP_SIZE="0GiB"
HIBERNATION_ENABLED="false"
swap_size_is_zero
! swapfile_required
printf '%s\n' 'ok - a zero swap size creates no swapfile'

SWAP_SIZE="32GiB"
! swap_size_is_zero
swapfile_required
printf '%s\n' 'ok - a non-zero swap size requires a swapfile'

# A hibernation image is the contents of RAM; a smaller swapfile cannot hold it,
# and the kernel only discovers that part way through suspending.
HIBERNATION_ENABLED="true"
get_memory_bytes() { printf '%s' $((64 * 1024 * 1024 * 1024)); }
if validate_swap_size_for_hibernation >/dev/null 2>&1; then
    printf '%s\n' 'not ok - a swapfile smaller than RAM was accepted' >&2
    exit 1
fi
printf '%s\n' 'ok - a swapfile smaller than RAM is refused'

get_memory_bytes() { printf '%s' $((16 * 1024 * 1024 * 1024)); }
validate_swap_size_for_hibernation >/dev/null
printf '%s\n' 'ok - a swapfile larger than RAM is accepted'

SWAP_SIZE="0GiB"
if validate_swap_size_for_hibernation >/dev/null 2>&1; then
    printf '%s\n' 'not ok - hibernation was accepted with no swap at all' >&2
    exit 1
fi
printf '%s\n' 'ok - hibernation with zero swap is refused'

# -- swapfile creation ---------------------------------------------------------

SWAP_SIZE="32GiB"
COMMANDS=''
create_swapfile
# btrfs mkswapfile, not dd plus mkswap: it clears copy-on-write and compression,
# both of which corrupt a swapfile. Lowercase suffix is the documented form.
[[ "${COMMANDS}" == *'btrfs filesystem mkswapfile --size 32768m /target/swap/swapfile'* ]]
[[ "${COMMANDS}" == *"swapon --priority ${SWAPFILE_SWAP_PRIORITY} /target/swap/swapfile"* ]]
printf '%s\n' 'ok - the swapfile is created with btrfs mkswapfile at a low priority'

SWAP_SIZE="0GiB"
COMMANDS=''
create_swapfile
[[ -z "${COMMANDS}" ]]
printf '%s\n' 'ok - no swapfile commands run when swap is disabled'

# -- fstab ---------------------------------------------------------------------

SWAP_SIZE="32GiB"
entry="$(swapfile_fstab_entry)"
[[ "${entry}" == *'/swap/swapfile none swap defaults,pri=10 0 0'* ]]
printf '%s\n' 'ok - the fstab entry pins the swapfile below zram'

SWAP_SIZE="0GiB"
[[ -z "$(swapfile_fstab_entry)" ]]
printf '%s\n' 'ok - no fstab swap entry without a swapfile'

# -- initramfs hooks -----------------------------------------------------------

LUKS_ENABLED="true"
HIBERNATION_ENABLED="true"
hooks="$(build_mkinitcpio_hooks)"

# systemd before sd-encrypt, sd-encrypt before filesystems, resume after
# filesystems. Any other order produces a machine that reaches the bootloader
# and then stops.
[[ "${hooks}" == *'systemd'*'sd-encrypt'*'filesystems'*'resume'* ]]
printf '%s\n' 'ok - hooks are ordered so unlocking and resuming both work'

HIBERNATION_ENABLED="false"
hooks="$(build_mkinitcpio_hooks)"
[[ "${hooks}" != *'resume'* ]]
printf '%s\n' 'ok - the resume hook is absent when hibernation is off'

LUKS_ENABLED="false"
hooks="$(build_mkinitcpio_hooks)"
[[ "${hooks}" != *'sd-encrypt'* ]]
printf '%s\n' 'ok - sd-encrypt is absent without encryption'

# -- resume parameters ---------------------------------------------------------

# shellcheck source=lib/bootloader.sh
source "${ROOT}/lib/bootloader.sh"

LUKS_ENABLED="true"
LUKS_NAME="cryptroot"
TPM2_ENABLED="true"
HIBERNATION_ENABLED="true"
SWAP_SIZE="32GiB"
get_swapfile_resume_offset() { printf '%s' '123456'; }

cmdline="$(limine_kernel_command_line 'UUID-HERE')"
# Both are required: resume= alone tells the kernel which device holds the image
# but not where it starts, and it cold-boots without reporting anything.
[[ "${cmdline}" == *'resume=/dev/mapper/cryptroot'* ]]
[[ "${cmdline}" == *'resume_offset=123456'* ]]
[[ "${cmdline}" == *'rootflags=subvol=@'* ]]
printf '%s\n' 'ok - the kernel command line carries both resume parameters'

HIBERNATION_ENABLED="false"
cmdline="$(limine_kernel_command_line 'UUID-HERE')"
[[ "${cmdline}" != *'resume'* ]]
printf '%s\n' 'ok - no resume parameters when hibernation is off'
