# AGENTS.md

## Project

This repository contains a robust, reproducible Arch Linux installer designed
primarily for a Framework Laptop 13.

The installer runs from the official Arch Linux live ISO in UEFI mode.

## Main goals

- Reproducible installation
- Modular task-based architecture
- Idempotent operations whenever possible
- Full dry-run support
- Strict validation before destructive operations
- Verification after every operation
- Clear logs and actionable errors
- LUKS2 encryption with TPM2 support
- Btrfs with subvolumes and snapshots
- Limine bootloader
- Framework Laptop optimizations
- Niri with Dank Material Shell desktop environment

## Coding rules

- Use Bash.
- Start executable scripts with `#!/usr/bin/env bash`.
- Use `set -Eeuo pipefail` in entry points.
- Quote all variable expansions unless intentional.
- Prefer `local` variables inside functions.
- Do not parse human-readable command output when a machine-readable format exists.
- Use `lsblk --json` or explicit columns where appropriate.
- Never silently ignore an error.
- Never execute destructive commands without validation and explicit confirmation.
- Every destructive operation must support dry-run.
- Hardware inspection must remain isolated in the appropriate library modules.
- Do not duplicate helpers already available in `lib/`.
- Keep tasks small and independently verifiable.
- Do not introduce dependencies without documenting them.

## Task API

Each task must expose:

- `task_<name>_name`
- `task_<name>_validate`
- `task_<name>_execute`
- `task_<name>_verify`
- `task_<name>_cleanup`
- `task_<name>_rollback`

Tasks must not call `exit`. They must return an error code and let the
orchestrator decide how to proceed.

## Safety

Never run real destructive storage commands during development or tests.

Commands such as the following must only run:

- from the official Arch live environment;
- against a validated installation target;
- outside dry-run mode;
- after explicit confirmation.

Examples:

- `wipefs`
- `sgdisk --zap-all`
- `cryptsetup luksFormat`
- `mkfs`
- `mkfs.btrfs`

Tests must use mocks, loop devices in an isolated integration environment, or
command capture. They must never target a physical disk.

## Testing

Before considering work complete, run when available:

```bash
bash -n install.sh
bash -n lib/*.sh
bash -n tasks/*.sh
shellcheck install.sh lib/*.sh tasks/*.sh tests/**/*.sh
```

Add tests for new behavior.

## Documentation

Update the relevant file under `docs/` whenever architecture, configuration,
storage, boot, security, recovery, desktop, or testing behavior changes.

## Git

- Make focused changes.
- Do not rewrite unrelated files.
- Do not delete existing functionality without explaining why.
- Do not commit unless explicitly requested.
- Show a summary of changed files and test results at the end.
