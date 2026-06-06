from __future__ import annotations

import shutil
import socket
from dataclasses import dataclass
from pathlib import Path


LOCAL_MODEL_RUNTIMES = {
    "ollama": {"commands": ("ollama",), "ports": (11434,), "api": "openai-compatible/ollama"},
    "lmstudio": {"commands": ("lmstudio", "lms"), "ports": (1234,), "api": "openai-compatible"},
    "vllm": {"commands": ("vllm", "python"), "ports": (8000,), "api": "openai-compatible"},
    "llamacpp": {"commands": ("llama-server", "llama-cli"), "ports": (8080,), "api": "openai-compatible"},
    "jan": {"commands": ("jan",), "ports": (1337,), "api": "openai-compatible"},
    "koboldcpp": {"commands": ("koboldcpp",), "ports": (5001,), "api": "kobold/openai-compatible"},
    "text-generation-webui": {"commands": ("text-generation-webui",), "ports": (5000, 7860), "api": "openai-compatible"},
    "localai": {"commands": ("local-ai", "localai"), "ports": (8080,), "api": "openai-compatible"},
}

CLI_AGENT_SURFACES = {
    "codex": ("codex",),
    "opencode": ("opencode",),
    "mistral_vibe": ("vibe", "vibe-acp"),
    "claude_code": ("claude",),
    "gemini_cli": ("gemini",),
    "qwen_code": ("qwen",),
    "aider": ("aider",),
    "cursor": ("cursor",),
    "windsurf": ("windsurf",),
}

CLI_PATH_HINTS = {
    "mistral_vibe": (
        "AppData/Local/Microsoft/WinGet/Packages/MistralAI.MistralVibe.ACP_*/*vibe-acp.exe",
    ),
    "aider": (
        ".local/bin/aider.exe",
        "AppData/Roaming/uv/tools/aider-chat/Scripts/aider.exe",
    ),
    "windsurf": (
        "AppData/Local/Programs/Windsurf/bin/windsurf.cmd",
        "AppData/Local/Programs/Windsurf/bin/windsurf.exe",
    ),
}

IDE_AGENT_SURFACES = {
    "vscode": ("code",),
    "vscodium": ("codium",),
    "cursor": ("cursor",),
    "windsurf": ("windsurf",),
    "zed": ("zed",),
    "jetbrains": ("idea", "pycharm", "webstorm"),
}

COMMON_MCP_SERVERS = {
    "filesystem": "local file access",
    "github": "PR comments, issues, repo automation",
    "browser": "browser control and snapshots",
    "figma": "Figma design control",
    "supabase": "database/backend operations",
    "blender": "3D automation",
    "memory": "persistent project memory",
}


@dataclass(frozen=True)
class SupportStatus:
    name: str
    available: bool
    kind: str
    detail: str = ""

    def to_dict(self) -> dict:
        return {"name": self.name, "available": self.available, "kind": self.kind, "detail": self.detail}


def _port_open(port: int, host: str = "127.0.0.1", timeout: float = 0.15) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _find_command(commands: tuple[str, ...], name: str = "") -> str:
    for cmd in commands:
        hit = shutil.which(cmd)
        if hit:
            return hit
    for hint in CLI_PATH_HINTS.get(name, ()):
        for root in (Path.home(), Path.home().parent / Path.home().name):
            matches = list(root.glob(hint))
            if matches:
                return str(matches[0])
    return ""


def discover_environment_support() -> dict:
    local_models = []
    for name, cfg in LOCAL_MODEL_RUNTIMES.items():
        commands = cfg["commands"]
        ports = cfg["ports"]
        command_hit = _find_command(commands)
        port_hit = next((port for port in ports if _port_open(port)), None)
        local_models.append(
            SupportStatus(
                name=name,
                available=bool(command_hit or port_hit),
                kind="local_model",
                detail=f"command={command_hit or 'missing'} port={port_hit or 'closed'} api={cfg['api']}",
            ).to_dict()
        )

    clis = []
    for name, commands in CLI_AGENT_SURFACES.items():
        command_hit = _find_command(commands, name)
        clis.append(
            SupportStatus(
                name,
                bool(command_hit),
                "cli_agent",
                command_hit or ",".join(commands),
            ).to_dict()
        )
    ides = []
    for name, commands in IDE_AGENT_SURFACES.items():
        command_hit = _find_command(commands, name)
        ides.append(
            SupportStatus(
                name,
                bool(command_hit),
                "ide_agent",
                command_hit or ",".join(commands),
            ).to_dict()
        )
    mcps = [
        SupportStatus(name, False, "mcp_server", desc).to_dict()
        for name, desc in COMMON_MCP_SERVERS.items()
    ]
    return {"local_models": local_models, "cli_agents": clis, "ide_agents": ides, "mcp_servers": mcps}
