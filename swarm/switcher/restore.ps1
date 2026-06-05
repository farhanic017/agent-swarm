# =============================================================================
#  Auto Model Switcher  ───  Restore Script
#  Copyright (c) 2026 Farhan Dhrubo  <farhaiee123@gmail.com>
#  License: GPL-3.0  —  https://github.com/farhanic017/auto-model-switcher
#
#  This program is free software. You may NOT remove this notice,
#  re-distribute as your own work, or sell without attribution.
# =============================================================================

param(
    [string]$InstallDir = "D:\open code\auto-model-switcher"
)

Write-Host ""
Write-Host "  Auto Model Switcher - Restore Script"
Write-Host "  ====================================="
Write-Host ""

# Ensure install dir exists
if (-not (Test-Path $InstallDir)) {
    New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null
}

# Check Python
$py = Get-Command python -ErrorAction SilentlyContinue
if (-not $py) {
    Write-Host "  [FAIL] Python not found. Install Python 3.10+ first." -ForegroundColor Red
    exit 1
}
Write-Host "  [OK] Python: $($py.Source)"

# Clone or copy
$scriptPath = Split-Path -Parent $MyInvocation.MyCommand.Path
if ($scriptPath -ne $InstallDir) {
    Write-Host "  Copying files to $InstallDir ..."
    Copy-Item -Path "$scriptPath\*" -Destination $InstallDir -Recurse -Force
}

# Run installer
Write-Host "  Running installer..."
& python "$InstallDir\install.py"
if ($LASTEXITCODE -ne 0) {
    Write-Host "  [FAIL] Installer failed." -ForegroundColor Red
    exit 1
}

# Create shortcuts
$ws = New-Object -ComObject WScript.Shell
$desktop = [Environment]::GetFolderPath("Desktop")

$shortcuts = @{
    "Auto Switcher - Status.lnk" = "python `"$InstallDir\switcher.py`" status"
    "Auto Switcher - Watch.lnk" = "start /B python `"$InstallDir\switcher.py`" watch"
    "Auto Switcher - Switch.lnk" = "python `"$InstallDir\switcher.py`" switch"
}

foreach ($name in $shortcuts.Keys) {
    $lnk = $ws.CreateShortcut("$desktop\$name")
    $lnk.TargetPath = "python"
    $lnk.Arguments = $shortcuts[$name]
    $lnk.WorkingDirectory = $InstallDir
    $lnk.WindowStyle = 7
    $lnk.Save()
    Write-Host "  [OK] Shortcut: $name"
}

# Add to PATH user env
$userPath = [Environment]::GetEnvironmentVariable("Path", "User")
if ($userPath -notlike "*$InstallDir*") {
    [Environment]::SetEnvironmentVariable("Path", "$userPath;$InstallDir", "User")
    Write-Host "  [OK] Added to PATH"
}

Write-Host ""
Write-Host "  ===== RESTORE COMPLETE ====="
Write-Host ""
Write-Host "  Quick commands:"
Write-Host "    ams status     - Show model health"
Write-Host "    ams switch     - Force model switch"
Write-Host "    ams watch      - Auto-watch (background)"
Write-Host ""
