param(
  [Parameter(ValueFromRemainingArguments = $true)]
  [string[]]$Prompt
)

$ErrorActionPreference = "Stop"

$originalHome = $HOME
$profileRoot = Join-Path $originalHome ".config\opencode-mistral"
$runtimeHome = Join-Path $profileRoot "home"
$configDir = Join-Path $profileRoot "opencode"
$configPath = Join-Path $configDir "opencode.jsonc"
$sourceConfig = Join-Path $originalHome ".config\opencode\opencode.jsonc"

New-Item -ItemType Directory -Force -Path $configDir | Out-Null
New-Item -ItemType Directory -Force -Path $runtimeHome | Out-Null

$python = @'
import json
import re
from pathlib import Path
import os

source = Path(os.environ["SOURCE_CONFIG"])
target = Path(os.environ["TARGET_CONFIG"])
raw = source.read_text(encoding="utf-8")

def strip_jsonc(text):
    out = []
    i = 0
    in_string = False
    line_comment = False
    block_comment = False
    while i < len(text):
        ch = text[i]
        if line_comment:
            if ch == "\n":
                line_comment = False
                out.append(ch)
            i += 1
            continue
        if block_comment:
            if ch == "*" and i + 1 < len(text) and text[i + 1] == "/":
                block_comment = False
                i += 2
                continue
            i += 1
            continue
        if in_string:
            if ch == "\\" and i + 1 < len(text):
                out.append(ch)
                out.append(text[i + 1])
                i += 2
                continue
            if ch == '"':
                in_string = False
            out.append(ch)
            i += 1
            continue
        if ch == '"':
            in_string = True
            out.append(ch)
            i += 1
            continue
        if ch == "/" and i + 1 < len(text) and text[i + 1] == "/":
            line_comment = True
            i += 2
            continue
        if ch == "/" and i + 1 < len(text) and text[i + 1] == "*":
            block_comment = True
            i += 2
            continue
        out.append(ch)
        i += 1
    return "".join(out)

data = json.loads(re.sub(r",\s*([}\]])", r"\1", strip_jsonc(raw)))
providers = data.get("provider", {})
if "mistral" not in providers:
    raise SystemExit("mistral provider is not configured in the source OpenCode config")

provider = dict(providers["mistral"])
options = dict(provider.get("options", {}))
if "baseUrl" in options:
    options["baseURL"] = options.pop("baseUrl")
provider["options"] = options

models = provider.get("models", {})
selected = {
    "mistral-small-latest": dict(models.get("mistral-small-latest", {})),
    "codestral-latest": dict(models.get("codestral-latest", {})),
}
for model_config in selected.values():
    model_config["limit"] = {"context": 32768, "output": 256}
provider["models"] = selected

minimal = {
    "$schema": "https://opencode.ai/config.json",
    "model": "mistral/mistral-small-latest",
    "small_model": "mistral/mistral-small-latest",
    "instructions": [],
    "plugin": [],
    "tools": {
        "bash": False,
        "edit": False,
        "glob": False,
        "grep": False,
        "list": False,
        "read": False,
        "task": False,
        "todowrite": False,
        "webfetch": False,
        "write": False,
    },
    "provider": {"mistral": provider},
    "compaction": {"auto": False, "prune": True, "reserved": 1000},
    "share": "disabled",
    "snapshot": False,
}

target.write_text(json.dumps(minimal, indent=2), encoding="utf-8")
'@

$env:SOURCE_CONFIG = $sourceConfig
$env:TARGET_CONFIG = $configPath
$python | python -

$env:XDG_CONFIG_HOME = $profileRoot
$env:HOME = $runtimeHome
$env:USERPROFILE = $runtimeHome

if (-not $Prompt -or $Prompt.Count -eq 0) {
  $Prompt = @("Reply exactly MISTRAL_OPENCODE_OK")
}

$events = opencode run --pure --no-replay --dir (Get-Location).Path --agent build --format json @Prompt
$sessionId = $null
foreach ($line in $events) {
  if (-not $line.Trim()) { continue }
  try {
    $event = $line | ConvertFrom-Json
    if ($event.sessionID) {
      $sessionId = $event.sessionID
    }
    if ($event.session -and $event.session.id) {
      $sessionId = $event.session.id
    }
    if ($event.part -and $event.part.type -eq "text" -and $event.part.text) {
      Write-Output $event.part.text
    }
  } catch {
    # Ignore non-JSON status lines from opencode.
  }
}

if (-not $sessionId) {
  $logDir = Join-Path $HOME ".local\share\opencode\log"
  $latestLog = Get-ChildItem -LiteralPath $logDir -Filter "*.log" -ErrorAction SilentlyContinue |
    Sort-Object LastWriteTime -Descending |
    Select-Object -First 1
  if ($latestLog) {
    $sessionLine = Get-Content -LiteralPath $latestLog.FullName |
      Select-String -Pattern "service=session id=(ses_[A-Za-z0-9]+)" |
      Select-Object -Last 1
    if ($sessionLine -and $sessionLine.Matches.Count -gt 0) {
      $sessionId = $sessionLine.Matches[0].Groups[1].Value
    }
  }
}

if ($sessionId) {
  $export = opencode export $sessionId | ConvertFrom-Json
  $texts = @()
  foreach ($message in $export.messages) {
    if ($message.info.role -ne "assistant") { continue }
    foreach ($part in $message.parts) {
      if ($part.type -eq "text" -and $part.text) {
        $texts += $part.text
      }
    }
  }
  if ($texts.Count -gt 0) {
    Write-Output ($texts -join "`n")
  }
}
