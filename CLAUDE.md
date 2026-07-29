# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Bash installer that provisions a reproducible Arch Linux system on a Framework Laptop (LUKS2 + Btrfs + Limine). The repository is currently a **scaffold**: roughly 2500 lines are implemented, and most tracked files (`tasks/*.sh`, `packages/*.list`, `services/*.list`, `templates/*`, `config/*.conf` except `system.conf`, and 7 of 9 `docs/*.md`) are intentionally empty placeholders committed to fix the layout.

## Running it

The scripts require an Arch Linux live ISO booted in UEFI mode, as root. They cannot be executed on a normal desktop — `validate_live_environment` (`lib/system.sh`) and `validate_environment` (`lib/validation.sh`) abort otherwise. Reason about the code by reading it; don't try to run the installer locally.

Working entry points:

```bash
sudo ./install.sh --inspect        # host + disk inspection, then exit
sudo ./install.sh --plan-storage   # validate and print the planned GPT layout, then exit
# flags: --dry-run  --verbose  --config FILE  --help
```

The default path (no mode flag) validates config and environment, then stops — `main()` ends with `"No installation operation has been implemented yet."` `--inspect` and `--plan-storage` are mutually exclusive.

There is no test suite, no CI, and no lint config. `install.sh` maintains `# shellcheck source=lib/…` directives, so the implied check is `shellcheck -x install.sh lib/*.sh` (`-x` is required for those directives to resolve); nothing runs it automatically.

## Architecture

`install.sh` is the only executable orchestrator. `lib/*.sh` are libraries — never executed directly, only sourced. The source order in `install.sh` is load-bearing: `logging` → `common` → `commands` → `config` → `ui` → `system` → `disk` → `partition` → `validation` (e.g. `load_config` calls `project_root` from `common.sh`).

Implemented modules:

| File | Role |
| --- | --- |
| `lib/logging.sh` | `info/success/warn/error/fatal/section` — all output goes through these |
| `lib/commands.sh` | `run_command` / `run_critical` / `capture_command` — the execution abstraction |
| `lib/common.sh` | `project_root`, `command_exists`, `is_root`, `is_uefi_system`, `trim` |
| `lib/config.sh` | `load_config` + `validate_config` |
| `lib/ui.sh` | `confirm`, `confirm_destructive_action`, `pause` (honor `INTERACTIVE_CONFIRMATION`) |
| `lib/system.sh` | host/firmware/CPU/memory probing, archiso and Secure Boot detection |
| `lib/disk.sh` | block-device properties, live-medium detection, installation-candidate safety |
| `lib/partition.sh` | size arithmetic, partition paths, storage-plan validation and display |
| `lib/validation.sh` | preflight gates (root, arch, UEFI, target disk, commands, network) |

`tasks/NN_*.sh` are numbered install stages, all still empty; the intended flow is environment → disk selection → storage → encryption → filesystem → mount → base system → configuration → packages → users → bootloader → security → cleanup → finish.

## Conventions

**Never call a mutating command directly.** Every system-changing command goes through `run_command` / `run_critical` from `lib/commands.sh`, which handles logging, `DRY_RUN`, verbose echo and failure reporting. This is the rule new code is most likely to break. All markers (`[DRY-RUN]`, `[COMMAND]`, `[CAPTURE]`) go to stderr so `$(…)` never captures them as data. `capture_command` is for **read-only commands only** and always executes, including in dry-run, because its output is consumed as a value.

Avoid `guard && return 1` as the last statement of a function — the function then exits with the guard's status and kills the caller under `set -e` unless every call site sits in a condition. Use explicit `if … then return 1; fi` (see `is_installation_candidate` in `lib/disk.sh`).

Every `lib/*.sh` file follows the same shape:

```bash
#!/usr/bin/env bash
# =====================
# Module: <name>
# Purpose: …
# Idempotent: Yes
# =====================
if [[ -n "${ARCH_INSTALLER_<NAME>_LOADED:-}" ]]; then
    return 0
fi
readonly ARCH_INSTALLER_<NAME>_LOADED="true"
```

Other conventions: `set -Eeuo pipefail` in executables; 4-space indent; `local` for every function variable; `${braced}` expansions; lower_snake_case function names; UPPER_SNAKE_CASE for config variables. Scripts must be idempotent. Comments explain *why*, not *what*.

`config/system.conf` is the single source of truth — scripts read it and never write to it. **Adding a config variable is a two-file edit**: declare it in `config/system.conf` *and* register it in the matching array inside `validate_config` (`required_variables`, `boolean_variables`, `size_variables`, `partition_label_variables`). Sizes must match `^[1-9][0-9]*(MiB|GiB|TiB)$`.

Hard-locked by `validate_config`, so changing them in config alone fails: `FILESYSTEM="btrfs"`, `BOOTLOADER="limine"`, and `BTRFS_SUBVOLUMES` must include `@ @home @snapshots @cache @log` — plus `@swap`, but only when `HIBERNATION_ENABLED=true` (a swapfile needs a no-CoW subvolume excluded from snapshots).

**Language:** documentation (`docs/`, `PROJECT.md`) is written in French; code, code comments, and user-facing script output are in English. Keep both as-is.

## Known scaffold quirks

- `PROJECT.md` sets a ~300-line-per-file cap as a stated convention; `lib/disk.sh` (~555) already exceeds it. Nothing enforces it.
- The six empty `config/*.conf` files (storage, security, packages, desktop, users, hooks) are **not** pending work. `config/system.conf` holds everything; the split was dropped in favour of the Python rewrite. Do not fill them.

## Direction

This Bash tree is a **fallback**. Active development is a full Python rewrite mirroring archinstall's structure (pydantic config models, Textual TUI with a plain-prompt fallback, `sgdisk`/`cryptsetup` via subprocess rather than `pyparted`), on the `python-rewrite` branch. `main` is frozen except for defect fixes until the Python path is proven on real hardware.

Do not build new features in Bash. The install stages named by the empty `tasks/*.sh` files will be implemented in Python, not here.
