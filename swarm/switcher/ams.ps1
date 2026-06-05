# =============================================================================
#  Auto Model Switcher  ───  Convenience CLI (ams status|switch|watch|discover)
#  Copyright (c) 2026 Farhan Dhrubo  <farhaiee123@gmail.com>
#  License: GPL-3.0  —  https://github.com/farhanic017/auto-model-switcher
#
#  This program is free software. You may NOT remove this notice,
#  re-distribute as your own work, or sell without attribution.
# =============================================================================

# Auto Model Switcher — CLI Wrapper
# Add the auto-model-switcher dir to your PATH, then use:
#   ams status
#   ams switch
#   ams watch
#   ams discover

param(
    [Parameter(Position=0)]
    [ValidateSet("status", "switch", "watch", "discover", "help")]
    [string]$Command = "help",

    [Parameter(Position=1)]
    [string]$Arg = ""
)

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Switcher = Join-Path $ScriptDir "switcher.py"

if (-not (Test-Path $Switcher)) {
    Write-Host "[ams] Error: switcher.py not found at $Switcher" -ForegroundColor Red
    exit 1
}

switch ($Command) {
    "status"   { python "$Switcher" status }
    "switch"   { python "$Switcher" switch $Arg }
    "watch"    { python "$Switcher" watch $Arg }
    "discover" { python "$Switcher" discover }
    default {
        @"
  Auto Model Switcher

  USAGE:
    ams status          Show model health and state
    ams switch [cli]    Force switch to next working model
    ams watch [secs]    Watch mode (background daemon)
    ams discover        List all discovered models

  EXAMPLES:
    ams status
    ams switch opencode
    ams watch 120
"@
    }
}
