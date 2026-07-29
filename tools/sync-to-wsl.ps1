# Copy the Python tree into WSL and run the test suite there.
#
# Why this exists: the development machine is Windows and has no Python, while
# the WSL Arch distribution has the same interpreter version as the Arch ISO.
# That distribution has automount and interop disabled, so there is no /mnt/c
# to work from — the source has to be piped in over stdin.
#
# Two quirks this script works around:
#   * PowerShell prepends a UTF-8 BOM when piping to a native command, so the
#     first three bytes are dropped on the Linux side.
#   * /tmp does not survive between `wsl` invocations, so the transfer and the
#     extraction happen in a single call.
#
# Usage:
#   .\tools\sync-to-wsl.ps1                # sync, then run pytest
#   .\tools\sync-to-wsl.ps1 -NoTest        # sync only
#   .\tools\sync-to-wsl.ps1 -Setup         # also create the venv and install deps

[CmdletBinding()]
param(
    [string]$Distro = 'archlinux',
    [string]$RemoteDir = '/home/reaper/afi',
    [switch]$NoTest,
    [switch]$Setup
)

# Not 'Stop': with interop disabled, wsl.exe writes a "Failed to translate"
# warning per Windows PATH entry to stderr. PowerShell 5.1 turns native stderr
# into NativeCommandError records, which would abort the script on noise.
# Exit codes are checked explicitly instead.
$ErrorActionPreference = 'Continue'

function Invoke-Wsl {
    param([string]$Command)

    & wsl -d $Distro --exec bash -c $Command 2>&1 |
        Where-Object { $_ -notmatch 'Failed to translate' } |
        ForEach-Object { "$_" }

    if ($LASTEXITCODE -ne 0) {
        throw "wsl command failed with exit code $LASTEXITCODE"
    }
}

$repo = Split-Path -Parent $PSScriptRoot
$work = Join-Path $env:TEMP 'afi-sync'
New-Item -ItemType Directory -Force -Path $work | Out-Null

$tar = Join-Path $work 'src.tgz'
$b64 = Join-Path $work 'src.b64'

Write-Host 'Packing...' -ForegroundColor Cyan
Remove-Item $tar, $b64 -ErrorAction SilentlyContinue
# packages/, services/ and templates/ are read at runtime, so leaving them out
# makes every package list resolve to empty and the tests pass against a system
# with no base packages.
tar -czf $tar -C $repo arch_framework tests packages services templates pyproject.toml
[IO.File]::WriteAllText(
    $b64,
    [Convert]::ToBase64String([IO.File]::ReadAllBytes($tar)),
    (New-Object Text.ASCIIEncoding)
)

Write-Host "Transferring to $Distro`:$RemoteDir ..." -ForegroundColor Cyan
$extract = "tr -d '\r\n' | tail -c +4 | base64 -d > /tmp/src.tgz && " +
           "mkdir -p $RemoteDir && " +
           "rm -rf $RemoteDir/arch_framework $RemoteDir/tests $RemoteDir/packages " +
           "$RemoteDir/services $RemoteDir/templates && " +
           "tar -xzf /tmp/src.tgz -C $RemoteDir && echo SYNC_OK"
Get-Content $b64 -Raw |
    & wsl -d $Distro --exec bash -c $extract 2>&1 |
    Where-Object { $_ -notmatch 'Failed to translate' }

if ($LASTEXITCODE -ne 0) {
    throw "transfer failed with exit code $LASTEXITCODE"
}

if ($Setup) {
    Write-Host 'Creating venv and installing dependencies...' -ForegroundColor Cyan
    Invoke-Wsl ("cd $RemoteDir && python3 -m venv .venv && " +
                "./.venv/bin/python -m pip install --quiet --upgrade pip && " +
                "./.venv/bin/python -m pip install --quiet pydantic textual pytest && " +
                "./.venv/bin/python -c 'import pydantic; print(pydantic.VERSION)'")
}

if (-not $NoTest) {
    Write-Host 'Running tests...' -ForegroundColor Cyan
    Invoke-Wsl "cd $RemoteDir && ./.venv/bin/python -m pytest -q"
}
