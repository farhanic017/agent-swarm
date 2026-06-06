from __future__ import annotations

import shutil
import socket
from dataclasses import dataclass


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
    "mistral_vibe": ("vibe",),
    "claude_code": ("claude",),
    "gemini_cli": ("gemini",),
    "qwen_code": ("qwen",),
    "aider": ("aider",),
    "cursor": ("cursor",),
    "windsurf": ("windsurf",),
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


def discover_environment_support() -> dict:
    local_models = []
    for name, cfg in LOCAL_MODEL_RUNTIMES.items():
        commands = cfg["commands"]
        ports = cfg["ports"]
        command_hit = next((cmd for cmd in commands if shutil.which(cmd)), "")
        port_hit = next((port for port in ports if _port_open(port)), None)
        local_models.append(
            SupportStatus(
                name=name,
                available=bool(command_hit or port_hit),
                kind="local_model",
                detail=f"command={command_hit or 'missing'} port={port_hit or 'closed'} api={cfg['api']}",
            ).to_dict()
        )

    clis = [
        SupportStatus(name, any(shutil.which(cmd) for cmd in commands), "cli_agent", ",".join(commands)).to_dict()
        for name, commands in CLI_AGENT_SURFACES.items()
    ]
    ides = [
        SupportStatus(name, any(shutil.which(cmd) for cmd in commands), "ide_agent", ",".join(commands)).to_dict()
        for name, commands in IDE_AGENT_SURFACES.items()
    ]
    mcps = [
        SupportStatus(name, False, "mcp_server", desc).to_dict()
        for name, desc in COMMON_MCP_SERVERS.items()
    ]
    return {"local_models": local_models, "cli_agents": clis, "ide_agents": ides, "mcp_servers": mcps}
