#!/usr/bin/env python3
#  Auto Model Switcher v2  ───  Always-On Smart Model Rotation
#  Copyright (c) 2026 Farhan Dhrubo  <farhaiee123@gmail.com>
#  License: GPL-3.0  —  https://github.com/farhanic017/auto-model-switcher
#
#  This program is free software. You may NOT remove this notice,
#  re-distribute as your own work, or sell without attribution.
# =============================================================================

"""
Auto Model Switcher v2 — Smart parallel model rotation across any CLI.

Auto-discovers models from CLI configs (opencode.jsonc, CLAUDE.md, etc.)
and environment variables. Checks ALL models in parallel (<2s). Scores them
by capability + health + cost. Picks the best working model instantly.

OpenRouter free-tier gate detection included ("buy N tokens" patterns).
When ALL models depleted, shows per-model recovery ETA.

Usage:
  python switcher.py status              # Show state + per-model ETAs
  python switcher.py switch [--task T]   # Pick best model for T (coding|chat|reasoning|general)
  python switcher.py watch               # Background daemon with auto-rotation
  python switcher.py discover            # Scan configs for models
"""

import json, os, sys, time, re, threading
from pathlib import Path
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

try:
    import requests
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "requests", "-q"])
    import requests

# ─── Paths ───────────────────────────────────────────────────────────────────

STATE_DIR = Path.home() / ".auto-model-switcher"
STATE_FILE = STATE_DIR / "state.json"
CONTEXT_FILE = STATE_DIR / "context.json"
LOG_FILE = STATE_DIR / "switcher.log"

CONFIG_PATHS = [
    Path.home() / ".config" / "opencode" / "opencode.jsonc",
    Path.home() / ".config" / "opencode" / "opencode.json",
    Path.cwd() / "opencode.jsonc",
    Path.cwd() / "opencode.json",
    Path.cwd() / "CLAUDE.md",
    Path.cwd() / ".cursorrules",
]

# OpenRouter free-tier gate patterns — models that say "buy X get Y free"
OPENROUTER_GATE_PATTERNS = [
    r"buy.*token.*free",
    r"purchase.*credit",
    r"insufficient.*credit",
    r"add.*funds",
    r"free.*tier.*limit",
]

# Model capability tiers for scoring
CAPABILITY_TIER = {
    "reasoning": ["o4", "o3", "deepseek", "kimi", "ring", "trinity", "laguna-m", "qwen3-next"],
    "general": ["gpt-4", "gpt-5", "claude", "gemma", "nemotron", "llama", "cobuddy", "qwen3-coder", "grok", "glm", "hermes"],
    "fast": ["flash", "mini", "nano", "lite", "instruct"],
}

# Model specialties — maps model keyword to task + strength bonus
MODEL_SPECIALTIES = [
    # Reasoning (deep thinking, math, logic)
    ("o4", "reasoning", 50), ("o3", "reasoning", 50),
    ("deepseek", "reasoning", 40), ("kimi", "reasoning", 40),
    ("ring", "reasoning", 35), ("trinity", "reasoning", 30),
    ("laguna-m", "reasoning", 25), ("qwen3-next", "reasoning", 25),
    # Coding (code gen, debugging, refactoring)
    ("qwen3-coder", "coding", 55), ("gpt-4.1", "coding", 45),
    ("deepseek", "coding", 35), ("gpt-4o", "coding", 30),
    ("gpt-5.1", "coding", 30), ("cobuddy", "coding", 25),
    ("grok-4.1-fast-reasoning", "coding", 30), ("grok-4.3", "coding", 25),
    # Chat / creative (conversation, writing, brainstorming)
    ("gemma-4-26b", "chat", 40), ("gemma-4-31b", "chat", 40),
    ("nemotron-3-super", "chat", 35), ("nemotron-3-nano", "chat", 30),
    ("llama-3.3", "chat", 30), ("gpt-5.4", "chat", 35),
    ("gpt-5.4-mini", "chat", 30), ("glm", "chat", 25),
    ("hermes", "chat", 25), ("dolphin", "chat", 20),
    ("lyria", "chat", 30), ("liquid/lfm-2.5", "chat", 20),
    # Fast / quick responses
    ("flash", "fast", 45), ("mini", "fast", 35),
    ("nano", "fast", 30), ("lite", "fast", 25),
    ("instruct", "fast", 20), ("phi-4", "fast", 25),
]

# ─── Logging ─────────────────────────────────────────────────────────────────

def log(msg: str):
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{ts}] {msg}\n")
    clean = msg.encode("ascii", "replace").decode()
    print(f"[switcher] {clean}")

# ─── State ───────────────────────────────────────────────────────────────────

def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except:
            pass
    return {"active": {}, "depleted": {}, "history": [], "last_switch": None, "hidden": [], "favorites": [], "recent": []}

def save_state(state: dict):
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2, default=str), encoding="utf-8")

def get_active(cli: str = "opencode") -> Optional[str]:
    return load_state().get("active", {}).get(cli)

def set_active(cli: str, model_key: str):
    state = load_state()
    state["active"][cli] = model_key
    state["last_switch"] = datetime.now().isoformat()
    save_state(state)

def mark_depleted(model_key: str, reason: str, cooldown_minutes: int = 30):
    state = load_state()
    now = datetime.now()

    # Extract retry-after seconds from reason string (e.g. "rate limited (429), retry in 120s")
    retry_secs = None
    m = re.search(r"retry in (\d+)s", reason)
    if m:
        retry_secs = int(m.group(1))
        cooldown_minutes = max(1, retry_secs // 60)

    state["depleted"][model_key] = {
        "reason": reason,
        "since": now.isoformat(),
        "cooldown_until": (now + timedelta(minutes=cooldown_minutes)).isoformat(),
        "retry_seconds": retry_secs,
    }
    state["history"].append({
        "model": model_key, "action": "depleted",
        "reason": reason, "time": now.isoformat(),
    })
    save_state(state)

def mark_recovered(model_key: str):
    state = load_state()
    state["depleted"].pop(model_key, None)
    state["history"].append({
        "model": model_key, "action": "recovered",
        "time": datetime.now().isoformat(),
    })
    save_state(state)

def is_depleted(model_key: str) -> bool:
    state = load_state()
    entry = state.get("depleted", {}).get(model_key)
    if not entry:
        return False
    cooldown = entry.get("cooldown_until")
    if cooldown and datetime.fromisoformat(cooldown) < datetime.now():
        state["depleted"].pop(model_key)
        save_state(state)
        return False
    return True

# ─── Hidden Models ──────────────────────────────────────────────────────────

def hide_model(model_key: str, reason: str = ""):
    """Hide a model so it never appears in chains or health checks."""
    state = load_state()
    hidden = state.get("hidden", [])
    if model_key not in hidden:
        hidden.append(model_key)
        state["hidden"] = hidden
        state["history"].append({
            "model": model_key, "action": "hidden",
            "reason": reason, "time": datetime.now().isoformat(),
        })
        save_state(state)
        log(f"Model hidden: {model_key}")
    return True

def unhide_model(model_key: str):
    """Unhide a model so it appears in chains again."""
    state = load_state()
    hidden = state.get("hidden", [])
    if model_key in hidden:
        hidden.remove(model_key)
        state["hidden"] = hidden
        state["history"].append({
            "model": model_key, "action": "unhidden",
            "time": datetime.now().isoformat(),
        })
        save_state(state)
        log(f"Model unhidden: {model_key}")
        return True
    return False

def get_hidden_models() -> list[str]:
    """Return the list of hidden model keys."""
    return list(load_state().get("hidden", []))

def is_hidden(model_key: str) -> bool:
    """Check if a model is hidden."""
    return model_key in load_state().get("hidden", [])

# ─── Favorites ──────────────────────────────────────────────────────────────

def toggle_favorite(model_key: str) -> bool:
    """Toggle a model as favorite. Returns True if now favorited, False if unfavorited."""
    state = load_state()
    favs = state.get("favorites", [])
    if model_key in favs:
        favs.remove(model_key)
        state["favorites"] = favs
        state["history"].append({
            "model": model_key, "action": "unfavorited",
            "time": datetime.now().isoformat(),
        })
        save_state(state)
        return False
    else:
        favs.append(model_key)
        state["favorites"] = favs
        state["history"].append({
            "model": model_key, "action": "favorited",
            "time": datetime.now().isoformat(),
        })
        save_state(state)
        return True

def set_favorite(model_key: str):
    """Explicitly favorite a model."""
    state = load_state()
    favs = state.get("favorites", [])
    if model_key not in favs:
        favs.append(model_key)
        state["favorites"] = favs
        state["history"].append({
            "model": model_key, "action": "favorited",
            "time": datetime.now().isoformat(),
        })
        save_state(state)

def unset_favorite(model_key: str):
    """Explicitly unfavorite a model."""
    state = load_state()
    favs = state.get("favorites", [])
    if model_key in favs:
        favs.remove(model_key)
        state["favorites"] = favs
        state["history"].append({
            "model": model_key, "action": "unfavorited",
            "time": datetime.now().isoformat(),
        })
        save_state(state)

def get_favorites() -> list[str]:
    """Return the list of favorited model keys."""
    return list(load_state().get("favorites", []))

def is_favorite(model_key: str) -> bool:
    """Check if a model is favorited."""
    return model_key in load_state().get("favorites", [])

# ─── Recent Models ──────────────────────────────────────────────────────────

def track_recent(model_key: str):
    """Track a model as recently used (max 10 recent)."""
    state = load_state()
    recent = state.get("recent", [])
    if model_key in recent:
        recent.remove(model_key)
    recent.insert(0, model_key)
    state["recent"] = recent[:10]
    state["history"].append({
        "model": model_key, "action": "recent",
        "time": datetime.now().isoformat(),
    })
    save_state(state)

def get_recent() -> list[str]:
    """Return the list of recently used model keys (most recent first)."""
    return list(load_state().get("recent", []))

# ─── MCP State Preservation ──────────────────────────────────────────────────

MCP_STATE_FILE = STATE_DIR / "mcp_state.json"


def save_mcp_tool_call(name: str, params: dict, result_hash: str = ""):
    """Record a tool execution so the next model knows what already ran."""
    state = _load_mcp_state()
    state["tools_executed"].append({
        "name": name,
        "params_summary": str(list(params.keys())[:3]) if params else "",
        "result_hash": result_hash,
        "timestamp": datetime.now().isoformat(),
    })
    _write_mcp_state(state)


def save_mcp_file_write(path: str, action: str = "write", result_hash: str = ""):
    """Record a file write/change to avoid re-execution after swap."""
    state = _load_mcp_state()
    norm = Path(path).resolve().as_posix()
    if not any(e["path"] == norm for e in state["file_writes"]):
        state["file_writes"].append({
            "path": norm, "action": action, "result_hash": result_hash,
            "timestamp": datetime.now().isoformat(),
        })
    _write_mcp_state(state)


def save_mcp_terminal_cmd(command: str, cwd: str = ""):
    """Record a terminal command so the next model knows current state."""
    state = _load_mcp_state()
    state["terminal_cmds"].append({
        "command": command[:200], "cwd": cwd,
        "timestamp": datetime.now().isoformat(),
    })
    _write_mcp_state(state)


def _load_mcp_state() -> dict:
    if MCP_STATE_FILE.exists():
        try:
            return json.loads(MCP_STATE_FILE.read_text(encoding="utf-8"))
        except:
            pass
    return {"tools_executed": [], "file_writes": [], "terminal_cmds": [],
            "conversation_summary": "", "last_model": None}


def _write_mcp_state(state: dict):
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    MCP_STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")


def build_mcp_handoff(prev_model: str, new_model: str) -> dict:
    """Build a handoff context for the incoming model. Includes what tools
    already ran, which files were modified, and terminal state so the new
    model doesn't re-execute already-done work."""
    mcp = _load_mcp_state()
    handoff = {
        "previous_model": prev_model,
        "new_model": new_model,
        "switched_at": datetime.now().isoformat(),
        "already_executed_tools": [
            {"name": t["name"], "params": t["params_summary"]}
            for t in mcp.get("tools_executed", [])
        ],
        "files_modified": [
            {"path": f["path"], "action": f["action"]}
            for f in mcp.get("file_writes", [])
        ],
        "terminal_history": [
            {"command": c["command"][:100], "cwd": c["cwd"]}
            for c in mcp.get("terminal_cmds", [])[-5:]
        ],
        "conversation_summary": mcp.get("conversation_summary", ""),
    }
    return handoff


def clear_mcp_state(new_model: str = ""):
    """Reset MCP state for a fresh session after switch. Tracks the new model."""
    state = _load_mcp_state()
    state["tools_executed"] = []
    state["terminal_cmds"] = []
    state["file_writes"] = []
    state["conversation_summary"] = ""
    state["last_model"] = new_model or state.get("last_model") or "unknown"
    _write_mcp_state(state)


# ─── Context Passing ─────────────────────────────────────────────────────────

def save_context(prev_model: str, new_model: str, reason: str, summary: str = ""):
    mcp_handoff = build_mcp_handoff(prev_model, new_model)
    ctx = {
        "previous_model": prev_model,
        "new_model": new_model,
        "switch_reason": reason,
        "summary": summary,
        "switched_at": datetime.now().isoformat(),
        "mcp": mcp_handoff,
    }
    CONTEXT_FILE.write_text(json.dumps(ctx, indent=2), encoding="utf-8")
    # Clean MCP state after handoff built so fresh state for the new model
    clear_mcp_state(new_model)

def load_context() -> dict:
    if CONTEXT_FILE.exists():
        try:
            return json.loads(CONTEXT_FILE.read_text(encoding="utf-8"))
        except:
            pass
    return {}

def get_recovery_eta() -> dict:
    """Returns per-model recovery ETA and next-available info."""
    state = load_state()
    depleted = state.get("depleted", {})
    active_key = get_active("opencode")

    now = datetime.now()
    etas = {}
    fastest = None
    active_depleted = False

    for key, info in depleted.items():
        cooldown = datetime.fromisoformat(info["cooldown_until"])
        remaining = (cooldown - now).total_seconds()
        minutes_left = max(0, int(remaining // 60))
        seconds_left = max(0, int(remaining))
        etas[key] = {
            "recovery_at": cooldown.isoformat(),
            "minutes_remaining": minutes_left,
            "seconds_remaining": seconds_left,
            "reason": info.get("reason", "unknown"),
            "retry_seconds": info.get("retry_seconds"),
        }
        if key == active_key:
            active_depleted = True
        if fastest is None or remaining < fastest["seconds"]:
            fastest = {"key": key, "seconds": remaining, "minutes": minutes_left}

    return {
        "all_depleted": active_depleted,
        "models": etas,
        "fastest_recovery": fastest,
        "checked_at": now.isoformat(),
    }

# ─── Config Discovery ────────────────────────────────────────────────────────

def parse_opencode_config(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    stripped = []
    in_string = False
    string_char = None
    i = 0
    while i < len(text):
        ch = text[i]
        if in_string:
            if ch == string_char and (i == 0 or text[i-1] != "\\"):
                in_string = False
            stripped.append(ch)
            i += 1
        elif ch in ('"', "'"):
            in_string = True
            string_char = ch
            stripped.append(ch)
            i += 1
        elif ch == "/" and i + 1 < len(text):
            if text[i+1] == "/":
                while i < len(text) and text[i] != "\n":
                    i += 1
            elif text[i+1] == "*":
                i += 2
                while i < len(text) and not (text[i] == "*" and i+1 < len(text) and text[i+1] == "/"):
                    i += 1
                i += 2
            else:
                stripped.append(ch)
                i += 1
        else:
            stripped.append(ch)
            i += 1
    return json.loads("".join(stripped))

def discover_providers() -> list[dict]:
    providers = []
    for cfg_path in CONFIG_PATHS:
        if not cfg_path.exists():
            continue
        try:
            ext = cfg_path.suffix.lower()
            if ext == ".md":
                discover_from_claude(cfg_path, providers)
            elif ext in (".json", ".jsonc"):
                discover_from_opencode(cfg_path, providers)
        except Exception as e:
            log(f"  skip {cfg_path.name}: {e}")
    discover_from_env(providers)
    discover_local_models(providers)
    return providers

def discover_from_opencode(path: Path, providers: list):
    cfg = parse_opencode_config(path)
    model_override = cfg.get("model")

    for provider_name, provider_cfg in cfg.get("provider", {}).items():
        opts = provider_cfg.get("options", {})
        api_key = opts.get("apiKey") or os.environ.get(f"{provider_name.upper().replace('-','_')}_API_KEY")

        for model_id, model_opts in provider_cfg.get("models", {}).items():
            is_free = (
                ":free" in model_id
                or provider_name in ("google-ai",)
                or model_id == "openrouter/free"
                or "free" in str(model_opts.get("tier", "")).lower()
            )
            deployment = model_opts.get("deployment", model_id)
            key = f"{provider_name}:{model_id}"
            is_active = model_id == model_override or deployment == model_override
            if model_override and not is_active:
                is_active = key.endswith(model_override) or model_id.endswith(model_override)

            providers.append({
                "key": key,
                "provider": provider_name,
                "model_id": model_id,
                "deployment": deployment,
                "api_key": api_key,
                "endpoint": opts.get("endpoint"),
                "is_free": is_free,
                "source": str(path),
                "is_active": is_active,
            })

def discover_from_claude(path: Path, providers: list):
    text = path.read_text(encoding="utf-8")
    m = re.search(r"model:\s*(\S+)", text)
    if m:
        providers.append({
            "key": f"claude:{m.group(1)}",
            "provider": "claude",
            "model_id": m.group(1),
            "deployment": m.group(1),
            "api_key": os.environ.get("ANTHROPIC_API_KEY"),
            "endpoint": None,
            "is_free": False,
            "source": str(path),
            "is_active": True,
        })

def discover_from_env(providers: list):
    seen_keys = {p["key"] for p in providers}
    env_mappings = {
        "OPENAI_API_KEY": ("openai", "gpt-4o"),
        "ANTHROPIC_API_KEY": ("claude", "claude-sonnet-4-20250514"),
        "GEMINI_API_KEY": ("google-ai", "gemini/gemini-2.5-flash-001"),
    }
    for env_var, (prov, model) in env_mappings.items():
        key = os.environ.get(env_var)
        if key and f"{prov}:{model}" not in seen_keys:
            providers.append({
                "key": f"{prov}:{model}", "provider": prov,
                "model_id": model, "deployment": model,
                "api_key": key, "endpoint": None,
                "is_free": prov == "google-ai",
                "source": "env", "is_active": False,
            })

# ─── Task Detection ──────────────────────────────────────────────────────────

def detect_task() -> str:
    """Auto-detect the likely task type from project context."""
    # 1. CLI override via --task flag (highest priority)
    override = os.environ.get("AUTO_SWITCHER_TASK")
    if override in ("coding", "chat", "reasoning", "general"):
        return override

    # 2. Context from previous switch
    ctx = load_context()
    if ctx.get("task"):
        return ctx["task"]

    # 3. Project context auto-detection
    cwd = Path.cwd()
    code_markers = [
        "package.json", "requirements.txt", "Cargo.toml",
        "go.mod", "pom.xml", "build.gradle", "CMakeLists.txt",
        "composer.json", "Gemfile",
    ]
    for marker in code_markers:
        if (cwd / marker).exists():
            return "coding"

    code_extensions = ["*.py", "*.js", "*.ts", "*.jsx", "*.tsx",
                       "*.rs", "*.go", "*.java", "*.cpp", "*.c",
                       "*.cs", "*.rb", "*.php", "*.swift"]
    for ext in code_extensions:
        if list(cwd.glob(ext)):
            return "coding"

    return "general"


def get_model_specialty(model_id: str) -> tuple[str, int]:
    """Return (task, strength) for a model, or (\"general\", 0) if unknown."""
    mid = model_id.lower()
    best_task = "general"
    best_strength = 0
    for keyword, task, strength in MODEL_SPECIALTIES:
        if keyword.lower() in mid and strength > best_strength:
            best_task = task
            best_strength = strength
    return best_task, best_strength


# ─── Model Scoring ───────────────────────────────────────────────────────────

def score_model(provider: dict, health: tuple, task: str = "general") -> int:
    """Score 0-250. Higher = better fit for the given task."""
    healthy, msg = health
    if not healthy:
        return 0

    score = 100  # base for healthy

    if provider["is_free"]:
        score += 50
    else:
        score += 20

    # Task-specific specialty (biggest factor)
    model_id = provider["model_id"].lower()
    spec_task, spec_strength = get_model_specialty(model_id)

    if spec_task == task:
        score += spec_strength
    elif spec_task == "reasoning" and task in ("coding", "general", "chat"):
        score += spec_strength // 2
    elif spec_task in ("coding", "chat", "fast") and task == "general":
        score += spec_strength // 2

    # Fallback capability bonus for unknown models
    if spec_task == "general":
        if any(t in model_id for t in CAPABILITY_TIER["reasoning"]):
            score += 25
        elif any(t in model_id for t in CAPABILITY_TIER["general"]):
            score += 15

    # Provider reliability
    prov = provider["provider"].lower()
    if "azure" in prov:
        score += 15
    elif "openrouter" in prov and provider["is_free"]:
        score -= 5  # free openrouter can be slow but not worthless

    # Deduct for known OpenRouter "gate" patterns
    if detect_free_tier_gate(provider, msg):
        score -= 60

    return score

# ─── Health Checks (Parallel) ────────────────────────────────────────────────

def _parse_retry_after(r: requests.Response) -> Optional[int]:
    """Extract retry-after seconds from 429/503 responses. Returns None if absent."""
    # requests.Response.headers is CaseInsensitiveDict — single check for Retry-After
    h = r.headers.get("Retry-After")
    if h:
        try:
            return max(0, int(h))
        except ValueError:
            # Try parsing as HTTP-date: "Wed, 21 Oct 2015 07:28:00 GMT"
            # Strip timezone manually to avoid %Z platform dependence
            try:
                parts = h.rsplit(" ", 1)
                date_str = parts[0]
                if len(parts) > 1:
                    date_str = date_str.rstrip(",")
                retry_dt = datetime.strptime(date_str, "%a, %d %b %Y %H:%M:%S")
                return max(0, int((retry_dt - datetime.now()).total_seconds()))
            except:
                pass
    # x-ratelimit-reset (common in OpenRouter/OpenAI) — Unix timestamp or ISO date
    h2 = r.headers.get("x-ratelimit-reset")
    if h2:
        try:
            reset_ts = float(h2)
            return max(0, int(reset_ts - time.time()))
        except ValueError:
            try:
                reset_dt = datetime.fromisoformat(h2.replace("Z", "+00:00"))
                return max(0, int((reset_dt - datetime.now()).total_seconds()))
            except:
                pass
    return None


def _build_rate_limit_msg(status: int, r: requests.Response) -> str:
    """Build a status message with retry-after info for 429/503."""
    retry = _parse_retry_after(r)
    retry_suffix = f", retry in {retry}s" if retry is not None else ""
    return f"rate limited ({status}){retry_suffix}"


def _check_openrouter(provider: dict, session: requests.Session) -> tuple[bool, str]:
    key = provider.get("api_key")
    if not key:
        return False, "no API key"
    try:
        r = session.get(
            "https://openrouter.ai/api/v1/auth/key",
            headers={"Authorization": f"Bearer {key}"},
            timeout=4,
        )
        if r.status_code == 200:
            data = r.json().get("data", {})
            credits = data.get("credits", 0)
            limit = data.get("limit", 0)

            if credits is not None and credits <= 0:
                return False, "0 credits remaining"
            if limit and credits and credits / limit < 0.05:
                return True, f"low credits (${credits:.2f})"

            return True, f"healthy (${credits:.2f} credits)"
        elif r.status_code == 429:
            return False, _build_rate_limit_msg(429, r)
        elif r.status_code == 402:
            return False, "payment required (402)"
        elif r.status_code == 401:
            return False, "invalid API key (401)"
        else:
            body = r.text[:200]
            return False, f"HTTP {r.status_code}: {body}"
    except Exception as e:
        return False, str(e)

def _check_google_ai(provider: dict, session: requests.Session) -> tuple[bool, str]:
    key = provider.get("api_key")
    if not key:
        return False, "no API key"
    model_id = provider["deployment"].replace("gemini/", "")
    try:
        r = session.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{model_id}:generateContent",
            params={"key": key},
            json={"contents": [{"parts": [{"text": "ok"}]}]},
            timeout=4,
        )
        if r.status_code == 200:
            return True, "healthy"
        elif r.status_code == 429:
            return False, _build_rate_limit_msg(429, r)
        elif r.status_code == 404:
            return False, f"model not found (404): {model_id}"
        elif r.status_code == 403:
            return False, "quota exceeded (403)"
        else:
            return False, f"HTTP {r.status_code}"
    except Exception as e:
        return False, str(e)

def _check_azure(provider: dict, session: requests.Session) -> tuple[bool, str]:
    key = provider.get("api_key")
    endpoint = provider.get("endpoint")
    if not key or not endpoint:
        return False, "missing API key or endpoint"
    try:
        r = session.get(
            f"{endpoint.rstrip('/')}/openai/models?api-version=2024-10-01-preview",
            headers={"api-key": key},
            timeout=5,
        )
        if r.status_code == 200:
            return True, "healthy"
        elif r.status_code == 429:
            return False, _build_rate_limit_msg(429, r)
        elif r.status_code == 403:
            return False, "access denied (403)"
        else:
            return False, f"HTTP {r.status_code}"
    except Exception as e:
        return False, str(e)

def _check_ollama(provider: dict, session: requests.Session) -> tuple[bool, str]:
    """Check Ollama local server. Distinguishes 'loading (cold start)' from dead."""
    try:
        r = session.get("http://localhost:11434/api/tags", timeout=3)
        if r.status_code != 200:
            return False, f"HTTP {r.status_code}"
        try:
            models = r.json().get("models", [])
        except (json.JSONDecodeError, ValueError):
            return True, "server up, unexpected response"
        desired = provider.get("model_id", "").replace("ollama:", "")

        # Warm-up ping — try a tiny generation even if model not in loaded list
        # (Ollama auto-loads unlisted models on first request, takes 10-15s into VRAM)
        if desired:
            try:
                wr = session.post(
                    "http://localhost:11434/api/generate",
                    json={"model": desired, "prompt": "ok", "stream": False,
                           "options": {"num_predict": 1, "temperature": 0}},
                    timeout=2,
                )
                if wr.status_code == 200:
                    return True, f"loaded and ready ({len(models)} models)"
                return True, f"model responding but HTTP {wr.status_code}"
            except requests.Timeout:
                return True, "loading (cold start into VRAM)"
            except requests.ConnectionError:
                return True, "loading (model restarting)"

        return True, f"running ({len(models)} models loaded)"
    except requests.ConnectionError:
        return False, "Ollama not running (http://localhost:11434)"
    except Exception as e:
        return False, str(e)


def _check_lm_studio(provider: dict, session: requests.Session) -> tuple[bool, str]:
    """Check LM Studio local server. Does a quick completion check."""
    try:
        r = session.get("http://localhost:1234/v1/models", timeout=3)
        if r.status_code != 200:
            return False, f"HTTP {r.status_code}"

        desired = provider.get("model_id", "local")
        try:
            wr = session.post(
                f"{provider.get('endpoint', 'http://localhost:1234')}/v1/chat/completions",
                json={"model": desired, "messages": [{"role": "user", "content": "ok"}],
                       "max_tokens": 1, "stream": False},
                timeout=3,
            )
            if wr.status_code == 200:
                return True, "loaded and ready"
            return True, f"running but completion HTTP {wr.status_code}"
        except requests.Timeout:
            return True, "loading (model cold-start into VRAM)"
        except requests.ConnectionError:
            return True, "loading (model restarting)"
        except (json.JSONDecodeError, ValueError):
            return True, "running (server up)"

    except requests.ConnectionError:
        return False, "LM Studio not running (http://localhost:1234)"
    except Exception as e:
        return False, str(e)


def _check_vllm(provider: dict, session: requests.Session) -> tuple[bool, str]:
    """Check vLLM/TGI server. Does a quick completion check."""
    endpoint = provider.get("endpoint", "http://localhost:8000").rstrip("/")
    try:
        r = session.get(f"{endpoint}/v1/models", timeout=3)
        if r.status_code != 200:
            return False, f"HTTP {r.status_code}"

        desired = provider.get("model_id", "local")
        try:
            wr = session.post(
                f"{endpoint}/v1/chat/completions",
                json={"model": desired, "messages": [{"role": "user", "content": "ok"}],
                       "max_tokens": 1, "stream": False},
                timeout=3,
            )
            if wr.status_code == 200:
                return True, "loaded and ready"
            return True, f"running but completion HTTP {wr.status_code}"
        except requests.Timeout:
            return True, "loading (model cold-start into VRAM)"
        except requests.ConnectionError:
            return True, "loading (model restarting)"
        except (json.JSONDecodeError, ValueError):
            return True, "running (server up)"

    except requests.ConnectionError:
        return False, f"vLLM not running ({endpoint})"
    except Exception as e:
        return False, str(e)


def discover_local_models(providers: list):
    """Scan for local model servers in parallel. Quick timeout per endpoint."""
    endpoints = {
        "ollama": ("http://localhost:11434", "api/tags", True),
        "lm-studio": ("http://localhost:1234", "v1/models", False),
        "vllm": ("http://localhost:8000", "v1/models", False),
    }
    session = _get_session()
    _local_lock = threading.Lock()

    def check_endpoint(name, base_url, check_path, is_ollama):
        key = f"{name}:local"
        if any(p["key"] == key for p in providers):
            return
        try:
            r = session.get(f"{base_url}/{check_path}", timeout=1.5)
            if r.status_code == 200:
                    if is_ollama:
                        model_list = r.json().get("models", [])
                        with _local_lock:
                            for m in model_list:
                                mname = m.get("name", "unknown")
                                providers.append({
                                    "key": f"ollama:{mname}", "provider": "ollama",
                                    "model_id": mname, "deployment": mname,
                                    "api_key": None, "endpoint": base_url,
                                    "is_free": True, "source": "local", "is_active": False,
                                })
                        if model_list:
                            log(f"Local: {len(model_list)} Ollama models found")
                    else:
                        with _local_lock:
                            providers.append({
                                "key": key, "provider": name,
                                "model_id": "local", "deployment": "local",
                                "api_key": None, "endpoint": base_url,
                                "is_free": True, "source": "local", "is_active": False,
                            })
                    log(f"Local: {name} running at {base_url}")
        except:
            pass

    with ThreadPoolExecutor(max_workers=3) as ex:
        for name, (base_url, check_path, is_ollama) in endpoints.items():
            ex.submit(check_endpoint, name, base_url, check_path, is_ollama)


def check_model(provider: dict) -> tuple[bool, str]:
    """Backward-compatible single-model check. Uses shared session."""
    s = _get_session()
    return _checked_model_with_session(provider, s)

# ─── Backward-compatible wrappers (used by tests) ─────────────────────────

def check_openrouter(provider: dict) -> tuple[bool, str]:
    s = _get_session()
    return _check_openrouter(provider, s)

def check_google_ai(provider: dict) -> tuple[bool, str]:
    s = _get_session()
    return _check_google_ai(provider, s)

def check_azure(provider: dict) -> tuple[bool, str]:
    s = _get_session()
    return _check_azure(provider, s)

def check_ollama(provider: dict) -> tuple[bool, str]:
    s = _get_session()
    return _check_ollama(provider, s)

def check_lm_studio(provider: dict) -> tuple[bool, str]:
    s = _get_session()
    return _check_lm_studio(provider, s)

def check_vllm(provider: dict) -> tuple[bool, str]:
    s = _get_session()
    return _check_vllm(provider, s)


def detect_free_tier_gate(provider: dict, msg: str) -> bool:
    """Detect if a free model is behind a 'buy tokens' gate."""
    if not provider.get("is_free"):
        return False
    if not msg:
        return False
    return any(re.search(p, msg.lower()) for p in OPENROUTER_GATE_PATTERNS)

CACHE_FILE = STATE_DIR / "health_cache.json"
CACHE_TTL = 120  # seconds before re-checking healthy models


def _load_health_cache() -> dict:
    if CACHE_FILE.exists():
        try:
            data = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
            now = time.time()
            return {
                k: (v["healthy"], v["msg"])
                for k, v in data.items()
                if now - v.get("time", 0) < CACHE_TTL
            }
        except:
            pass
    return {}


def _save_health_cache(results: dict):
    now = time.time()
    data = {
        k: {"healthy": h, "msg": m, "time": now}
        for k, (h, m) in results.items() if h  # only cache healthy
    }
    CACHE_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


_CHECK_SESSION = None

def _get_session() -> requests.Session:
    global _CHECK_SESSION
    if _CHECK_SESSION is None:
        s = requests.Session()
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=10, pool_maxsize=20,
            max_retries=0
        )
        s.mount("https://", adapter)
        s.mount("http://", adapter)
        _CHECK_SESSION = s
    return _CHECK_SESSION


def check_all_parallel(chain: list[dict], cached_health: dict = None) -> dict:
    """Check ALL models in parallel. Uses cache for all healthy models, not just active.
    Deduplicates by API key — only one health check per provider+key combo."""
    results = {}
    cache = cached_health or {}

    unique_checks = {}
    for p in chain:
        dedup_key = f"{p['provider']}:{p.get('api_key', 'none')[:8]}"
        if dedup_key not in unique_checks:
            unique_checks[dedup_key] = []

        key = p["key"]
        if is_depleted(key):
            continue

        # Use cache for ANY healthy model, not just active
        cached = cache.get(key)
        if cached and cached[0]:
            results[key] = cached
            continue

        unique_checks[dedup_key].append(p)

    if not any(v for v in unique_checks.values()):
        return results

    session = _get_session()
    dedup_results = {}
    with ThreadPoolExecutor(max_workers=10) as ex:
        futures = {}
        for dedup_key, providers in unique_checks.items():
            if providers:
                futures[ex.submit(_checked_model_with_session, providers[0], session)] = dedup_key

        for future in as_completed(futures):
            dedup_key = futures[future]
            try:
                dedup_results[dedup_key] = future.result()
            except Exception as e:
                dedup_results[dedup_key] = (False, str(e))

    for dedup_key, providers in unique_checks.items():
        health = dedup_results.get(dedup_key, (False, "no check"))
        for p in providers:
            results[p["key"]] = health

    return results


def _checked_model_with_session(provider: dict, session: requests.Session) -> tuple:
    """Wrapper that passes the shared session to check functions."""
    prov_name = provider["provider"].lower()
    if prov_name == "openrouter":
        return _check_openrouter(provider, session)
    elif "google" in prov_name:
        return _check_google_ai(provider, session)
    elif "azure" in prov_name:
        return _check_azure(provider, session)
    elif prov_name == "ollama":
        return _check_ollama(provider, session)
    elif prov_name in ("lm-studio", "lm_studio"):
        return _check_lm_studio(provider, session)
    elif prov_name == "vllm":
        return _check_vllm(provider, session)
    else:
        return True, "no health check available"

# ─── Config Writers ──────────────────────────────────────────────────────────

def update_opencode_config(model_key: str) -> bool:
    for cfg_path in CONFIG_PATHS:
        if not cfg_path.exists() or cfg_path.suffix not in (".json", ".jsonc"):
            continue
        try:
            text = cfg_path.read_text(encoding="utf-8")
            provider, model_id = model_key.split(":", 1)
            text = re.sub(r'"model"\s*:\s*"[^"]*"', f'"model": "{model_id}"', text)
            cfg_path.write_text(text, encoding="utf-8")
            log(f"opencode config updated: model -> {model_id} (in {cfg_path.name})")
            return True
        except Exception as e:
            log(f"failed to update {cfg_path.name}: {e}")
    return False

def update_claude_config(model_key: str) -> bool:
    claude_path = Path.cwd() / "CLAUDE.md"
    if not claude_path.exists():
        return False
    try:
        text = claude_path.read_text(encoding="utf-8")
        model_id = model_key.split(":", 1)[1] if ":" in model_key else model_key
        if re.search(r"model:\s*\S+", text):
            text = re.sub(r"model:\s*\S+", f"model: {model_id}", text)
        else:
            text += f"\nmodel: {model_id}\n"
        claude_path.write_text(text, encoding="utf-8")
        log(f"Claude config updated: model -> {model_id}")
        return True
    except Exception as e:
        log(f"failed to update CLAUDE.md: {e}")
        return False

# ─── Core Logic ──────────────────────────────────────────────────────────────

def build_chain(providers: list[dict]) -> list[dict]:
    hidden = set(get_hidden_models())
    free_models = [p for p in providers if p["is_free"] and p["key"] not in hidden]
    paid_models = [p for p in providers if not p["is_free"] and p["key"] not in hidden]
    return free_models + paid_models

def discover():
    log("Discovering models...")
    providers = discover_providers()
    if not providers:
        discover_from_env(providers)
    if not providers:
        print("  No models discovered. Set up API keys in opencode.jsonc or env vars.")
        return []

    seen = {}
    unique = []
    for p in providers:
        if p["key"] not in seen:
            seen[p["key"]] = True
            unique.append(p)

    print(f"\n  Discovered {len(unique)} models across {len(set(p['provider'] for p in unique))} providers:\n")
    for p in unique:
        active = "*" if p.get("is_active") else " "
        free_tag = "[FREE]" if p["is_free"] else "[PAID]"
        spec, _ = get_model_specialty(p["model_id"])
        print(f"  {active} {free_tag:7s} {spec:10s} {p['key']:<45} from {p['source']}")
    print()
    return unique

def status():
    state = load_state()
    providers = discover_providers()
    chain = build_chain(providers)
    active_key = get_active("opencode")
    task = detect_task()

    print(f"\n  Auto Model Switcher v2 — Status\n")
    print(f"  State file: {STATE_FILE}")
    print(f"  Models discovered: {len(providers)}")
    print(f"  Depleted models: {len(state.get('depleted', {}))}")
    print(f"  Last switch: {state.get('last_switch', 'never')}")
    print(f"  Detected task: {task}\n")

    if active_key:
        spec, _ = get_model_specialty(active_key)
        print(f"  Active model: {active_key}  (specialty: {spec})")
    else:
        print(f"  Active model: (not set)")

    # Recovery ETA if all depleted
    eta = get_recovery_eta()
    if eta["all_depleted"] and state.get("depleted"):
        fastest = eta.get("fastest_recovery")
        if fastest:
            secs = fastest.get("seconds_remaining", fastest["minutes"] * 60)
            if secs < 120:
                print(f"\n  All models depleted. Next recovery: ~{secs}s ({fastest['key']})")
            else:
                print(f"\n  All models depleted. Next recovery: ~{fastest['minutes']} min ({fastest['key']})")
        print(f"\n  Per-model recovery ETAs:")
        for key, info in sorted(eta["models"].items(), key=lambda x: x[1]["minutes_remaining"]):
            reason_short = info["reason"][:40]
            secs = info.get("seconds_remaining", info["minutes_remaining"] * 60)
            if secs < 120:
                print(f"    {key:<50} {secs:3d}s  ({reason_short})")
            else:
                print(f"    {key:<50} {info['minutes_remaining']:3d} min  ({reason_short})")
        print()

    if state.get("depleted") and not eta["all_depleted"]:
        print(f"\n  Some models depleted:")
        for key, info in state["depleted"].items():
            until = info.get("cooldown_until", "?")
            print(f"    X {key:<50} cooldown until {until[:19]}")
        print()

    print(f"  Model chain (free first, priority order):\n")
    for i, p in enumerate(chain, 1):
        key = p["key"]
        is_act = key == active_key
        is_dep = is_depleted(key)
        spec, _ = get_model_specialty(p["model_id"])
        status_icon = "*" if is_act else " "
        dep_icon = " [depleted]" if is_dep else ""
        free_tag = "F" if p["is_free"] else "P"
        match_tag = " <<< BEST FOR TASK" if is_act else ""
        print(f"  {i:2d}. {status_icon} [{free_tag}] {spec:10s} {key:<45}{dep_icon}{match_tag}")
    print()
    return chain

def switch(cli: str = "opencode", silent: bool = False) -> bool:
    providers = discover_providers()
    chain = build_chain(providers)

    if not chain:
        log("No models available to switch to!")
        return False

    task = detect_task()
    active_key = get_active(cli)
    log(f"Active model: {active_key} | Task: {task}")

    # Phase 1: Check ALL models in parallel (<4s)
    log(f"Checking {len(chain)} models in parallel...")
    cached = _load_health_cache()
    health_results = check_all_parallel(chain, cached_health=cached)
    _save_health_cache(health_results)

    # Phase 2: Score and rank by task relevance
    scored = []
    for p in chain:
        key = p["key"]
        health = health_results.get(key, (False, "no check"))
        healthy, msg = health

        # Detect OpenRouter free-tier gate (e.g., "buy 10 tokens get 1000 free")
        if healthy and detect_free_tier_gate(p, msg):
            log(f"  {key}: free-tier gate detected ({msg})")
            mark_depleted(key, f"free-tier gate: {msg}", cooldown_minutes=60)
            healthy = False

        # Local model cold-start: loading into VRAM, don't deplete — schedule re-check
        is_cold_start = "cold start" in msg.lower()
        if is_cold_start and healthy:
            log(f"  {key}: cold start detected ({msg}), scheduling warm-up re-check")
            scored.append((score_model(p, health, task) - 30, p, msg))
            continue

        if not healthy:
            if not is_depleted(key):
                mark_depleted(key, msg, cooldown_minutes=30)
            continue

        if is_depleted(key):
            continue

        score = score_model(p, health, task)
        if score > 0:
            scored.append((score, p, msg))

    scored.sort(key=lambda x: -x[0])

    if not scored:
        if not silent:
            eta = get_recovery_eta()
            print("\n  [FAIL] All models are depleted.")
            if eta.get("fastest_recovery"):
                f = eta["fastest_recovery"]
                secs = f.get("seconds_remaining", f["minutes"] * 60)
                if secs < 120:
                    print(f"  Next recovery: ~{secs}s ({f['key']})")
                else:
                    print(f"  Next recovery: ~{f['minutes']} min ({f['key']})")
            print(f"\n  Per-model recovery:")
            for key, info in sorted(eta["models"].items(), key=lambda x: x[1]["minutes_remaining"]):
                secs = info.get("seconds_remaining", info["minutes_remaining"] * 60)
                if secs < 120:
                    print(f"    {key:<50} {secs:3d}s  ({info['reason'][:50]})")
                else:
                    print(f"    {key:<50} {info['minutes_remaining']:3d} min  ({info['reason'][:50]})")
            print()
        log("All models depleted!")
        return False

    # Phase 3: Pick best model for the detected task
    best_score, best_provider, best_msg = scored[0]
    best_key = best_provider["key"]

    prev_key = active_key
    set_active(cli, best_key)

    if prev_key and prev_key != best_key:
        save_context(prev_key, best_key, f"auto-switch: {best_msg}",
                     f"Switched from {prev_key} to {best_key} ({best_msg})")
        log(f"Context saved: {prev_key} -> {best_key}")

    if cli == "opencode":
        update_opencode_config(best_key)
    elif cli == "claude":
        update_claude_config(best_key)

    spec, spec_str = get_model_specialty(best_provider["model_id"])
    free_tag = "FREE" if best_provider["is_free"] else "PAID"
    if not silent:
        print(f"\n  [OK] Switched to: {best_key}")
        print(f"       Tier: {free_tag} | Specialty: {spec} | Task: {task} | Score: {best_score}")
        print(f"       Health: {best_msg}")
        placed = next((i+1 for i, (s, p, m) in enumerate(scored) if p["key"] == best_key), None)
        print(f"       Matches: #{placed} of {len(scored)} working models")
        print(f"       Reason: best {spec} model for {task} task\n")

    log(f"Switched {cli} -> {best_key} (score={best_score}, spec={spec}, task={task}, {best_msg})")
    return True

def watch(interval: int = 120):
    log(f"Starting watch mode (check every {interval}s)...")
    print(f"  Watching model health every {interval}s. Ctrl+C to stop.\n")

    try:
        while True:
            providers = discover_providers()
            chain = build_chain(providers)
            active_key = get_active("opencode")

            if active_key:
                health_results = check_all_parallel(chain)
                active_health = health_results.get(active_key)

                if active_health and not active_health[0]:
                    log(f"Active model {active_key} failed: {active_health[1]}")
                    mark_depleted(active_key, active_health[1])
                    print(f"  [FAIL] {active_key}: {active_health[1]}")
                    print(f"  Switching...")
                    switch("opencode")
                else:
                    log(f"Active model {active_key}: {active_health[1] if active_health else 'ok'}")
            else:
                log("No active model, running initial switch...")
                switch("opencode")

            # Recover expired depleted models
            state = load_state()
            for key in list(state.get("depleted", {}).keys()):
                entry = state["depleted"][key]
                cooldown = entry.get("cooldown_until")
                if cooldown and datetime.fromisoformat(cooldown) < datetime.now():
                    provider = next((p for p in chain if p["key"] == key), None)
                    if provider:
                        healthy, msg = check_model(provider)
                        if healthy and not detect_free_tier_gate(provider, msg):
                            mark_recovered(key)
                            log(f"Model {key} recovered: {msg}")
                            print(f"  [OK] {key} recovered: {msg}")

            time.sleep(interval)
    except KeyboardInterrupt:
        log("Watch mode stopped by user")
        print("\n  Watch mode stopped.")

# ─── CLI ─────────────────────────────────────────────────────────────────────

def main():
    STATE_DIR.mkdir(parents=True, exist_ok=True)

    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return

    cmd = args[0]
    task_override = None
    silent = "--silent" in args

    if "--task" in args:
        idx = args.index("--task")
        if idx + 1 < len(args):
            task_override = args[idx + 1]

    if task_override:
        os.environ["AUTO_SWITCHER_TASK"] = task_override

    # Strip known flags from args for positional parsing
    known_flags = {"--task", "--silent"}
    positional = [a for a in args if a not in known_flags and not any(
        args[i] == "--task" and i + 1 < len(args) and args[i + 1] == a
        for i in range(len(args))
    )]
    if not positional:
        positional = args[:1]  # keep cmd at least

    if cmd == "discover":
        discover()
    elif cmd == "status":
        status()
    elif cmd == "switch":
        cli = positional[1] if len(positional) > 1 else "opencode"
        switch(cli, silent=silent)
    elif cmd == "watch":
        interval = int(positional[1]) if len(positional) > 1 else 120
        watch(interval)
    else:
        print(f"Unknown command: {cmd}")
        print(__doc__)

if __name__ == "__main__":
    main()
