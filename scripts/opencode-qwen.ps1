param(
  [Parameter(ValueFromRemainingArguments = $true)]
  [string[]]$Prompt
)

$ErrorActionPreference = "Stop"

$profileRoot = Join-Path $HOME ".config\opencode-qwen"
$configDir = Join-Path $profileRoot "opencode"
$configPath = Join-Path $configDir "opencode.jsonc"
$sourceConfig = Join-Path $HOME ".config\opencode\opencode.jsonc"

New-Item -ItemType Directory -Force -Path $configDir | Out-Null

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

def provider_subset(name, models):
    provider = dict(providers[name])
    options = dict(provider.get("options", {}))
    if "baseUrl" in options:
        options["baseURL"] = options.pop("baseUrl")
    provider["options"] = options
    provider["models"] = {model: provider.get("models", {}).get(model, {}) for model in models}
    for model_config in provider["models"].values():
        model_config["limit"] = {"context": 32768, "output": 512}
    return provider

minimal = {
    "$schema": "https://opencode.ai/config.json",
    "model": "cloudflare/@cf/qwen/qwen2.5-coder-32b-instruct",
    "small_model": "cloudflare/@cf/qwen/qwen2.5-coder-32b-instruct",
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
    "provider": {
        "cloudflare": provider_subset("cloudflare", ["@cf/qwen/qwen2.5-coder-32b-instruct"]),
        "groq": provider_subset("groq", ["qwen/qwen3-32b"]),
    },
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
$env:HOME = $HOME
$env:USERPROFILE = $HOME

if (-not $Prompt -or $Prompt.Count -eq 0) {
  $Prompt = @("Reply exactly OPENCODE_QWEN_OK")
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
    if ($event.part -and $event.part.type -eq "text" -and $event.part.text) {
      Write-Output $event.part.text
    }
  } catch {
    # Ignore non-JSON status lines from opencode.
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
