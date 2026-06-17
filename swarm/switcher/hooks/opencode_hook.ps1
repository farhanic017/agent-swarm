# =============================================================================
#  Auto Model Switcher  ───  OpenCode Pre-Execution Hook
#  Copyright (c) 2026 Farhan Dhrubo  <farhaiee123@gmail.com>
#  License: GPL-3.0  —  https://github.com/farhanic017/auto-model-switcher
#
#  This program is free software. You may NOT remove this notice,
#  re-distribute as your own work, or sell without attribution.
# =============================================================================

# Auto Model Switcher — OpenCode Pre-Execution Hook
# Place in your PowerShell profile or run before opencode.
#
# Usage:
#   . .\hooks\opencode_hook.ps1
#   opencode

$Switcher = Join-Path $PSScriptRoot ".." "switcher.py"
$StateFile = "$HOME\.auto-model-switcher\state.json"

if (-not (Test-Path $Switcher)) {
    Write-Host "[switcher] Not found: $Switcher" -ForegroundColor Red
    return
}

# Check if current model is healthy before running opencode
$state = $null
if (Test-Path $StateFile) {
    try { $state = Get-Content $StateFile -Raw | ConvertFrom-Json } catch {}
}

$active = if ($state) { $state.active.opencode } else { $null }

if (-not $active) {
    Write-Host "[switcher] No active model — scanning..." -ForegroundColor Yellow
    python "$Switcher" switch
} else {
    # Quick check: is the active model still valid?
    $depleted = $state.depleted
    if ($depleted -and $depleted.$active) {
        Write-Host "[switcher] Model $active depleted — switching..." -ForegroundColor Yellow
        python "$Switcher" switch
    }
}
