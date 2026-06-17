# =============================================================================
#  Auto Model Switcher  ───  Universal CLI Wrapper (PowerShell)
#  Copyright (c) 2026 Farhan Dhrubo  <farhaiee123@gmail.com>
#  License: GPL-3.0  —  https://github.com/farhanic017/auto-model-switcher
#
#  This program is free software. You may NOT remove this notice,
#  re-distribute as your own work, or sell without attribution.
# =============================================================================

# Auto Model Switcher — Universal CLI Wrapper
# =============================================
# Usage: dot-source this in your PowerShell profile, then:
#   opencode <args>     # auto-switches before running
#   claude <args>       # auto-switches before running
#   cursor <args>       # auto-switches before running
#
# Or run a single command with auto-switch:
#   .\auto-switch.ps1 opencode --version

param(
    [Parameter(Position=0, Mandatory=$false)]
    [string]$TargetCli = "",

    [Parameter(ValueFromRemainingArguments=$true)]
    [string[]]$CliArgs = @()
)

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Switcher = Join-Path $ScriptDir "switcher.py"
$StateFile = "$HOME\.auto-model-switcher\state.json"

# ─── Health Check ────────────────────────────────────────────────────────────
function Test-ModelHealth {
    if (-not (Test-Path $StateFile)) { return $false }
    try {
        $state = Get-Content $StateFile -Raw | ConvertFrom-Json
        $active = $state.active.opencode
        $depleted = $state.depleted
        if (-not $active) { return $false }
        if ($depleted -and $depleted.$active) { return $false }
        return $true
    } catch { return $false }
}

# ─── Auto-Switch ─────────────────────────────────────────────────────────────
function Invoke-AutoSwitch {
    Write-Host "[auto-switch] Checking model health..." -ForegroundColor Cyan
    $result = python "$Switcher" switch 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "[auto-switch] Ready" -ForegroundColor Green
    } else {
        Write-Host "[auto-switch] WARNING: $result" -ForegroundColor Yellow
    }
}

# ─── Main ────────────────────────────────────────────────────────────────────
if (-not (Test-ModelHealth)) {
    Invoke-AutoSwitch
}

# ─── Known CLI paths (auto-detected if missing) ──────────────────────────────
$__KNOWN_CLIS = @{
    "opencode" = @(
        "$env:LOCALAPPDATA\Programs\@opencode-aidesktop\OpenCode.exe",
        "$env:LOCALAPPDATA\Programs\opencode\OpenCode.exe",
        "opencode.exe"
    )
    "claude"    = @("claude.exe", "$env:LOCALAPPDATA\Programs\claude\claude.exe")
    "cursor"    = @("cursor.exe", "$env:LOCALAPPDATA\Programs\cursor\cursor.exe")
    "aider"     = @("aider.exe", "$env:LOCALAPPDATA\Programs\aider\aider.exe")
    "windsurf"  = @("windsurf.exe", "$env:LOCALAPPDATA\Programs\windsurf\windsurf.exe")
    "continue"  = @("continue.exe", "$env:LOCALAPPDATA\Programs\continue\continue.exe")
}

function global:__ams_resolve_cli {
    param([string]$Name)
    $paths = $__KNOWN_CLIS[$Name.ToLower()]
    if (-not $paths) { return $Name }  # Unknown CLI, pass through
    foreach ($p in $paths) {
        if (Get-Command $p -ErrorAction SilentlyContinue) { return $p }
        if (Test-Path $p) { return $p }
    }
    return $Name  # Fallback to bare name
}

# Auto-generate wrapper functions for all known CLIs + any in PATH
$__ams_registered = @{}
foreach ($cliName in $__KNOWN_CLIS.Keys) {
    $safeName = $cliName -replace '[^a-zA-Z0-9_]', ''
    if (-not $__ams_registered[$safeName]) {
        $__ams_registered[$safeName] = $true
        $__cliPath = __ams_resolve_cli $cliName
        $__wrapper = @"
function global:$safeName {
    python "$Switcher" switch --silent
    & '$__cliPath' @args
}
"@
        Invoke-Expression $__wrapper
    }
}

# Also wrap any unknown CLI found in PATH (future-proof for new agents)
Get-Command -CommandType Application -ErrorAction SilentlyContinue | ForEach-Object {
    $name = $_.Name -replace '\.(exe|bat|ps1)$', ''
    if ($name -and -not $__ams_registered[$name] -and $name -notmatch '^(python|powershell|cmd|wscript|cscript|conhost|dllhost|svchost|rundll32|taskhost|sihost|fontdrv|smss|csrss|wininit|lsass|services|spoolsv)') {
        $__ams_registered[$name] = $true
        $__fullPath = $_.Source
        $__wrapper = @"
function global:$name {
    python "$Switcher" switch --silent
    & '$__fullPath' @args
}
"@
        Invoke-Expression $__wrapper
    }
}

# If a specific CLI was requested, run it now
if ($TargetCli) {
    $cliPath = __ams_resolve_cli $TargetCli
    if ($CliArgs) {
        & $cliPath @CliArgs
    } else {
        & $cliPath
    }
}

Remove-Variable -Name __ams_registered, __ams_* -ErrorAction SilentlyContinue
