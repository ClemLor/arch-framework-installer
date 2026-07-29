# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

An installer that provisions a reproducible Arch Linux system on a Framework Laptop: LUKS2 + Btrfs subvolumes + Limine + TPM2 unlock + hibernation. Structure mirrors archinstall so the layout is familiar, but the implementation is our own.

**Two trees.** `arch_framework/` (Python) is where all work happens. `install.sh` + `lib/*.sh` (Bash) is a frozen fallback kept until the Python path boots on real hardware — do not add features there.

Status: 209 tests pass. **Nothing has ever booted** — no VM, no hardware. TPM2 enrolment and hibernation resume have never executed.

## You cannot run this here

The dev machine is Windows with **no Python interpreter** (only the Store stubs). Tests run in WSL Arch, which has 3.14 — the ISO's version.

```powershell
.\tools\sync-to-wsl.ps1 -Setup   # first time: venv + deps
.\tools\sync-to-wsl.ps1          # sync, then pytest
.\tools\sync-to-wsl.ps1 -NoTest
```

That WSL distro has `automount` and `interop` disabled, so there is no `/mnt/c` — the script pipes source over stdin, strips the BOM PowerShell prepends, and does transfer plus extract in one `wsl` call because `/tmp` does not survive between invocations. Do not try to `cd /mnt/c/...` in WSL.

Interactive `wsl -d archlinux --exec bash -c '...'` mangles quotes (default shell is fish). Base64-encode the script and decode it inside instead.

```bash
python -m arch_framework --tui                       # guided menu
python -m arch_framework --inspect                   # read-only
python -m arch_framework --plan-storage              # read-only, one stdout document
python -m arch_framework --install --dry-run --config saved.json
python -m arch_framework --install --config saved.json --creds creds.json
# --renderer plain|textual  --devices-from FIXTURE  --verbose
```

## The rules that matter

**Nothing mutates the system outside `lib/command.py` and `lib/target.py`.** A direct `subprocess.run`, or a `Path.write_text` into `/mnt`, bypasses dry-run and creates files while claiming to change nothing. Writing `/mnt/etc/fstab` is as destructive as `mkfs`.

Three operations, deliberately distinct:

| | mutates | in dry-run |
| --- | --- | --- |
| `run` | yes | does not execute |
| `capture` | no | **executes anyway** — output is consumed as a value |
| `derived` | no | returns a marked placeholder (`<UUID-of-…>`) |

`capture` must execute or every decision made from its output is corrupted by a placeholder. `derived` exists because in dry-run the filesystem was never created, so `blkid` returns nothing and fstab/crypttab/limine.conf would render blank and unreviewable.

Long or interactive commands need `stream=True` (`pacstrap`, `mkinitcpio`, `arch-chroot`). Captured output on a multi-minute command looks like a hang and hides a pacman prompt.

**`stdout` carries only data; all logging goes to `stderr`.** Tests assert stdout stays clean. `--plan-storage` is the exception by design: it is one coherent stdout document so it can be redirected.

**Secrets go on stdin, never as arguments** (the process list is world-readable), and never into the saved configuration.

## Where the destructive decision is taken

Three layers exist; only the third counts:

1. the menu hides ineligible disks, with the reason;
2. `guided.run` asks the user to type the disk name;
3. **`partitioning.guard_target` refuses immediately before `wipefs`.**

A config can be hand-written, copied between machines, or replayed months later against different hardware. Re-check against the disk as it is now — never inherit the menu's verdict. It raises rather than warns, and fires in dry-run too.

A real install also **refuses recorded devices** (`FixtureSource`). Without that guard, a test driving the CLI would reach `wipefs` on this machine's own disk.

Four independent guards: whole disk, not the live medium, not USB, not removable. Test each separately — a combined test passes while three are broken. `read_only_mode` relaxes *only* the mount check; a `WARNING` verdict still reports `writable=False`.

## Device facts come from a source, never directly

`SystemSource` shells out to `lsblk --json` / `findmnt --json`; `FixtureSource` reads the same shape from a file. That is what makes the safety layer testable with no disks.

Do not trust lsblk's `pkname` — it is undocumented whether `--paths` prefixes it. `flatten()` records the parent itself under `_parent`; `normalise_device_name()` handles either form. Binary files (efivars) use `read_bytes` and `files_base64` in fixtures: decoding as UTF-8 with replacement collapses byte runs and shifts the offset the Secure Boot check indexes.

## Configuration

pydantic models in `lib/models/`, serialised to JSON. Adding a setting is a one-file change.

- single-field rules → on the field
- cross-field rules → on `InstallConfig` (hibernation requires `@swap`; TPM2 requires a recovery key)
- rules needing observed hardware → explicit methods (`validate_capacity`, `validate_hibernation`)

Serialisation is deterministic, so a saved config is a reproducibility artefact. Edits go through `Draft.update`, which revalidates the whole document and reverts on rejection — field-by-field mutation bypasses the cross-field rules.

`Draft.from_saved` marks a loaded config fully answered. The unanswered state exists to stop the profile's **placeholder disk** being installed onto, not to make someone re-answer decisions; gating replay behind walking the menu again would defeat the point of the project.

Locked: `FILESYSTEM=btrfs`, `BOOTLOADER=limine`, subvolumes must include `@ @home @snapshots @cache @log`, plus `@swap` when hibernation is on.

## Menu

Entries are data in `tui/entries.py`. Both renderers walk the same registry. Adding one means two edits: the `MenuEntry` in `build_registry` **and** the key in `ENTRY_KEYS` — an assertion keeps them in sync, because a key missing from `ENTRY_KEYS` is silently unanswered on reload.

Textual is present on the ISO only because archinstall depends on it — a transitive guarantee. The plain renderer is first-class, and is the only one that works over serial, SSH, or with a screen reader.

## Install stages

Eleven named stages in `lib/installer.py`, recorded in `/run/…state.json` and skipped on resume. Resuming with a different config is refused.

Ordering is a safety property, asserted by tests: recovery key added **and acknowledged** before TPM2 enrolment. A TPM2 seal is bound to firmware and Secure Boot state; a firmware update can invalidate it, so enrolling first leaves a window where the machine is lost. The original passphrase is never removed.

## Verification

`tests/golden/install-commands.txt` is a full dry-run command sequence. It pins `sgdisk` units and argument order, `cryptsetup` options, subvolume creation order and mount order — uncheckable any other way without hardware to destroy. On a diff: read it, update the file only if the change is intended.

Reviewing it has already caught three real bugs (package lists never read, `fish` missing so the account could not log in, a pid in the keyfile name making the journal unreproducible). Take it seriously.

`sgdisk` accepts `K/M/G/T/P` and **rejects `MiB`** — `Size.sgdisk()` exists for this. `btrfs mkswapfile` suffixes are lowercase.

## Conventions

Documentation (`docs/`, `PROJECT.md`) in **French**; code, comments and user-facing output in **English**.

Comments explain *why*, not *what*. `PROJECT.md` states a ~300-line-per-file cap; nothing enforces it and some files exceed it.

`.gitattributes` pins LF for `.sh` and `.py` — a CRLF shebang fails on the ISO with `$'\r': command not found`.

`packages/*.list` is one package per line with `#` comments. `base`, `firmware`, `framework` are populated and mandatory; the other six are **deliberately empty** — selecting one warns rather than silently installing nothing. Nothing verifies a package name exists in the repos.

`limine-mkinitcpio-hook` is **AUR-only** and cannot be pacstrap'd; it is reported as a post-first-boot step and the system must boot without it.

The six empty `config/*.conf` files are obsolete, not pending. Do not fill them.
