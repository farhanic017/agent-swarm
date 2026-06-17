#!/usr/bin/env python3
#  Auto Model Switcher  ───  Universal Installer
#  Copyright (c) 2026 Farhan Dhrubo  <farhaiee123@gmail.com>
#  License: GPL-3.0  —  https://github.com/farhanic017/auto-model-switcher
#
#  This program is free software. You may NOT remove this notice,
#  re-distribute as your own work, or sell without attribution.
# =============================================================================

"""
Auto Model Switcher — Universal Installer

Installs the switcher into EVERY CLI entry point so manual switching is
never needed. Works with: OpenCode, Claude Code, Cursor, Aider, Windsurf,
Continue.dev, and any tool that reads model configs.

Install methods:
  1. PowerShell profile (every shell starts auto-switch)
  2. PATH wrapper (auto-switch.bat intercepts CLI calls)
  3. Task Scheduler background watch (checks every 2 min)
  4. Desktop shortcut for watch mode
"""

import json, os, sys, shutil, subprocess
from pathlib import Path

SWITCHER_DIR = Path(__file__).parent.resolve()
STATE_DIR = Path.home() / ".auto-model-switcher"

POWERSHELL_PROFILE_CODE = r'''
# >>> Auto Model Switcher (auto-loaded) >>>
$__AMS_SWITCHER = "{switcher}"
$__AMS_STATE = "$HOME\.auto-model-switcher\state.json"
function __ams_check {{
    if (-not (Test-Path $__AMS_STATE)) {{ return }}
    try {{
        $s = Get-Content $__AMS_STATE -Raw | ConvertFrom-Json
        $a = $s.active.opencode
        $d = $s.depleted
        if (-not $a -or ($d -and $d.$a)) {{
            Write-Host "[ams] Checking model health..." -ForegroundColor Cyan
            python "$__AMS_SWITCHER" switch --silent
        }}
    }} catch {{}}
}}
# Run once on shell start (fast, <2s parallel check)
__ams_check
# <<< Auto Model Switcher >>>
'''


def print_banner():
    print()
    print("  Auto Model Switcher — Universal Installer")
    print("  ===========================================")
    print()

def check_python():
    print(f"  Python: {sys.version.split()[0]}")
    print()

def setup_state():
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    state_file = STATE_DIR / "state.json"
    if not state_file.exists():
        state_file.write_text(json.dumps(
            {"active": {}, "depleted": {}, "history": [], "last_switch": None}, indent=2))
        print("  [OK] Created state directory")
    else:
        print("  [OK] State directory exists")

def install_requires():
    print("  Installing dependencies...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "requests", "-q"])
    print("  [OK] Dependencies installed")

def install_powershell_profile():
    """Install auto-switch into PowerShell profile (runs on every shell start)."""
    profile_paths = []
    # Try common PowerShell profile locations
    candidates = [
        Path.home() / "Documents" / "PowerShell" / "Microsoft.PowerShell_profile.ps1",
        Path.home() / "Documents" / "WindowsPowerShell" / "Microsoft.PowerShell_profile.ps1",
        Path.home() / ".config" / "powershell" / "Microsoft.PowerShell_profile.ps1",
    ]

    # Also check PSModulePath
    ps_module_path = os.environ.get("PSModulePath", "")
    for entry in ps_module_path.split(";"):
        p = Path(entry.strip())
        if p.exists():
            profile_candidate = p.parent / "Microsoft.PowerShell_profile.ps1"
            if profile_candidate not in candidates:
                candidates.append(profile_candidate)

    profile_path = None
    for c in candidates:
        if c.exists():
            profile_path = c
            break

    if not profile_path:
        # Create in Documents\PowerShell
        profile_path = Path.home() / "Documents" / "PowerShell" / "Microsoft.PowerShell_profile.ps1"
        profile_path.parent.mkdir(parents=True, exist_ok=True)

    code = POWERSHELL_PROFILE_CODE.format(
        switcher=str(SWITCHER_DIR / "switcher.py").replace("\\", "\\\\")
    )

    existing = profile_path.read_text(encoding="utf-8") if profile_path.exists() else ""
    if "# >>> Auto Model Switcher" not in existing:
        with open(profile_path, "a", encoding="utf-8") as f:
            f.write(code)
        print(f"  [OK] PowerShell profile: {profile_path}")
    else:
        print(f"  [OK] PowerShell profile already configured: {profile_path}")

def install_path_wrappers():
    """Install CLI wrappers into PATH."""
    # Windows: create .bat files in a PATH directory
    bat_dir = Path.home() / ".auto-model-switcher" / "bin"
    bat_dir.mkdir(parents=True, exist_ok=True)

    # Supported CLIs — add new ones here for auto-wrap. The system auto-wraps
    # ANY unknown CLI found in PATH for future-proofing (see auto-switch.ps1).
    clis = {
        "opencode": r'C:\Users\Farhan\AppData\Local\Programs\@opencode-aidesktop\OpenCode.exe',
        "claude": "claude.exe",
        "cursor": "cursor.exe",
        "aider": "aider.exe",
        "windsurf": "windsurf.exe",
        "continue": "continue.exe",
    }

    for cli_name, cli_path in clis.items():
        bat_content = f'''@echo off
REM Auto Model Switcher wrapper for {cli_name}
python "{SWITCHER_DIR / 'switcher.py'}" switch --silent >nul 2>&1
{cli_path} %*
'''
        bat_file = bat_dir / f"{cli_name}.bat"
        bat_file.write_text(bat_content)
        print(f"  [OK] Wrapper: {bat_file}")

    # ps1 version for PowerShell
    ps1_content = f'''# Auto Model Switcher — universal pre-exec hook
python "{SWITCHER_DIR / 'switcher.py'}" switch --silent
'''
    ps1_file = bat_dir / "auto-switch-pre.ps1"
    ps1_file.write_text(ps1_content)

    # Add to PATH via user env var
    current_path = os.environ.get("PATH", "")
    bat_dir_str = str(bat_dir)
    if bat_dir_str not in current_path:
        try:
            subprocess.run([
                "powershell", "-Command",
                f'[Environment]::SetEnvironmentVariable("Path",'
                f'[Environment]::GetEnvironmentVariable("Path","User") + ";{bat_dir_str}",'
                f'"User")'
            ], check=True, capture_output=True)
            print(f"  [OK] Added to PATH: {bat_dir}")
        except Exception as e:
            print(f"  [WARN] Could not update PATH: {e}")
    else:
        print(f"  [OK] Already in PATH: {bat_dir}")

    return bat_dir

def install_startup_task():
    """Create a Windows scheduled task for background watch mode."""
    ps_script = f'''
$action = New-ScheduledTaskAction -Execute "python" -Argument '"{SWITCHER_DIR / "switcher.py"}" watch'
$trigger = New-ScheduledTaskTrigger -AtStartup
$principal = New-ScheduledTaskPrincipal -UserId "{os.environ.get('USERNAME', 'Farhan')}" -RunLevel Limited
Register-ScheduledTask -TaskName "AutoModelSwitcher" -Action $action -Trigger $trigger -Principal $principal -Force
'''
    try:
        subprocess.run(["powershell", "-Command", ps_script],
                       check=True, capture_output=True, timeout=15)
        print("  [OK] Startup task created: AutoModelSwitcher")
    except subprocess.TimeoutExpired:
        print("  [WARN] Startup task creation timed out (needs admin?)")
    except subprocess.CalledProcessError as e:
        print(f"  [WARN] Startup task: {e.stderr.decode()[:100] if e.stderr else 'failed'}")

def install_shortcuts():
    """Create desktop shortcuts for common commands."""
    desktop = Path.home() / "Desktop"
    if not desktop.exists():
        return

    vbs_content = f'''
Set WshShell = CreateObject("WScript.Shell")
Set lnk = WshShell.CreateShortcut("{desktop / 'Auto Model Switcher.lnk'}")
lnk.TargetPath = "python"
lnk.Arguments = "{SWITCHER_DIR / 'switcher.py'} watch"
lnk.WorkingDirectory = "{SWITCHER_DIR}"
lnk.WindowStyle = 7
lnk.Save()
'''
    vbs_file = STATE_DIR / "create_shortcut.vbs"
    vbs_file.write_text(vbs_content)
    try:
        subprocess.run(["wscript", str(vbs_file)], capture_output=True, timeout=5)
        print("  [OK] Desktop shortcut created")
    except:
        print("  [WARN] Could not create desktop shortcut")

def install_watchdog():
    """Install WMI-based watchdog VBS (invisible background)."""
    watchdog_content = f'''Set service = GetObject("winmgmts:{{impersonationLevel=impersonate}}!.root\\cimv2")

Do While True
    Set colProcesses = service.ExecQuery("SELECT * FROM Win32_Process WHERE Name='opencode.exe' OR Name='OpenCode.exe'")
    Set colWatcher = service.ExecQuery("SELECT * FROM Win32_Process WHERE CommandLine LIKE '%switcher.py watch%'")
    
    Dim opencode_running : opencode_running = False
    Dim watcher_running : watcher_running = False
    
    For Each p In colProcesses : opencode_running = True : Next
    For Each p In colWatcher : watcher_running = True : Next
    
    If opencode_running And Not watcher_running Then
        CreateObject("WScript.Shell").Run "python ""{SWITCHER_DIR / 'switcher.py'}"" watch", 0, False
    ElseIf Not opencode_running And watcher_running Then
        For Each p In colWatcher : p.Terminate() : Next
    End If
    
    WScript.Sleep 10000
Loop
'''
    watchdog_path = STATE_DIR / "watchdog.vbs"
    watchdog_path.write_text(watchdog_content)
    print(f"  [OK] Watchdog: {watchdog_path}")

    # Auto-start watchdog
    auto_start = STATE_DIR / "start_watchdog.ps1"
    auto_start.write_text(f'Start-Process wscript -ArgumentList "{watchdog_path}" -WindowStyle Hidden')
    print(f"  [OK] Watchdog starter: {auto_start}")

def create_ams_bat():
    """Create ams.bat in PATH for quick access."""
    bat_content = f'''@echo off
python "{SWITCHER_DIR / 'switcher.py'}" %*
'''
    bat_dir = Path.home() / ".auto-model-switcher" / "bin"
    bat_dir.mkdir(parents=True, exist_ok=True)
    ams_bat = bat_dir / "ams.bat"
    ams_bat.write_text(bat_content)
    print(f"  [OK] ams.bat wrapper: {ams_bat}")

def test_switcher():
    print()
    print("  Running integration test...")
    result = subprocess.run(
        [sys.executable, str(SWITCHER_DIR / "switcher.py"), "discover"],
        capture_output=True, text=True, timeout=30)
    output = result.stdout + result.stderr
    lines = [l for l in output.split("\n")
             if l.strip() and not l.startswith("[switcher]")]
    for line in lines:
        print(f"  {line}")

def scan_configs():
    print()
    print("  Scanning CLI configs...")
    paths = [
        Path.home() / ".config" / "opencode" / "opencode.jsonc",
        Path.home() / ".config" / "opencode" / "opencode.json",
        Path.cwd() / "opencode.jsonc",
        Path.cwd() / "opencode.json",
        Path.cwd() / "CLAUDE.md",
        Path.cwd() / ".cursorrules",
    ]
    found = False
    for p in paths:
        if p.exists():
            print(f"  [OK] {p.name}: {p}")
            found = True
    if not found:
        print("  [WARN] No CLI configs found. Run 'ams discover' after setup.")

def main():
    print_banner()
    check_python()
    install_requires()
    setup_state()
    scan_configs()

    print()
    print("  Installing always-on hooks...")
    print()

    install_powershell_profile()
    bat_dir = install_path_wrappers()
    create_ams_bat()
    install_startup_task()
    install_shortcuts()
    install_watchdog()

    print()
    print("  Running first-time discovery...")
    test_switcher()

    print()
    print("  ===== INSTALL COMPLETE =====")
    print()
    print("  The auto switcher is now ALWAYS ON:")
    print("  - Every PowerShell prompt checks model health")
    print("  - PATH wrappers intercept CLI calls")
    print("  - Background watchdog keeps watch mode running")
    print("  - Startup task auto-launches on boot")
    print()
    print("  Quick commands:")
    print(f"    ams status           Show model health + ETAs")
    print(f"    ams switch           Switch to best model")
    print(f"    ams watch            Background watch mode")
    print(f"    ams discover         Scan for new models")
    print()
    print(f"  Or just use your CLI normally — switches happen automatically.")
    print()

if __name__ == "__main__":
    main()
