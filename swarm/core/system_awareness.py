"""
System Awareness Tools — detect hardware specs, RAM, storage, VRAM,
and auto-detect available providers/models.

The swarm self-awareness system knows what hardware it's running on
and can adapt its behavior accordingly (e.g., avoid memory-heavy operations
on low-RAM systems).
"""

from __future__ import annotations

import json
import os
import platform
import subprocess
from typing import Any


def _get_system_info() -> dict[str, Any]:
    """Get basic system information."""
    info = {
        "platform": platform.system(),
        "platform_release": platform.release(),
        "platform_version": platform.version(),
        "architecture": platform.machine(),
        "processor": platform.processor(),
        "python_version": platform.python_version(),
        "hostname": platform.node(),
    }
    return info


def _get_ram_info() -> dict[str, Any]:
    """Get RAM information."""
    try:
        import psutil
        mem = psutil.virtual_memory()
        return {
            "total_gb": round(mem.total / (1024**3), 2),
            "available_gb": round(mem.available / (1024**3), 2),
            "used_gb": round(mem.used / (1024**3), 2),
            "percent_used": mem.percent,
        }
    except ImportError:
        pass

    # Fallback: platform-specific
    if platform.system() == "Windows":
        try:
            result = subprocess.run(
                ["wmic", "memorychip", "get", "Capacity"],
                capture_output=True, text=True, timeout=5
            )
            lines = [l.strip() for l in result.stdout.strip().split("\n") if l.strip() and l.strip() != "Capacity"]
            total_bytes = sum(int(l) for l in lines if l.isdigit())
            return {
                "total_gb": round(total_bytes / (1024**3), 2),
                "available_gb": None,
                "used_gb": None,
                "percent_used": None,
            }
        except Exception:
            pass

    return {"total_gb": None, "available_gb": None, "used_gb": None, "percent_used": None}


def _get_storage_info() -> dict[str, Any]:
    """Get disk storage information."""
    try:
        import psutil
        disks = []
        for part in psutil.disk_partitions():
            try:
                usage = psutil.disk_usage(part.mountpoint)
                disks.append({
                    "device": part.device,
                    "mountpoint": part.mountpoint,
                    "total_gb": round(usage.total / (1024**3), 2),
                    "free_gb": round(usage.free / (1024**3), 2),
                    "used_gb": round(usage.used / (1024**3), 2),
                    "percent_used": round(usage.percent, 1),
                })
            except PermissionError:
                continue
        return {"disks": disks}
    except ImportError:
        pass

    return {"disks": []}


def _get_vram_info() -> dict[str, Any]:
    """Get GPU/VRAM information."""
    # Try nvidia-smi first
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total,memory.free,memory.used",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            gpus = []
            for line in result.stdout.strip().split("\n"):
                if line.strip():
                    parts = [p.strip() for p in line.split(",")]
                    if len(parts) >= 4:
                        gpus.append({
                            "name": parts[0],
                            "total_mb": int(parts[1]),
                            "free_mb": int(parts[2]),
                            "used_mb": int(parts[3]),
                        })
            return {"gpus": gpus, "source": "nvidia-smi"}
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    # Try rocm-smi for AMD
    try:
        result = subprocess.run(
            ["rocm-smi", "--showmeminfo", "vram"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            return {"gpus": [], "source": "rocm-smi", "raw": result.stdout[:500]}
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    # Try wmic for Windows
    if platform.system() == "Windows":
        try:
            result = subprocess.run(
                ["wmic", "path", "win32_videocontroller", "get", "Name,AdapterRAM"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                return {"gpus": [], "source": "wmic", "raw": result.stdout[:500]}
        except Exception:
            pass

    return {"gpus": [], "source": "none"}


def _detect_providers() -> list[dict[str, Any]]:
    """Auto-detect available API providers from environment."""
    providers = []

    # OpenAI
    if os.environ.get("OPENAI_API_KEY"):
        providers.append({"name": "openai", "has_key": True, "base_url": "https://api.openai.com/v1"})

    # Anthropic
    if os.environ.get("ANTHROPIC_API_KEY"):
        providers.append({"name": "anthropic", "has_key": True})

    # Google
    if os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY"):
        providers.append({"name": "google", "has_key": True})

    # Fireworks
    if os.environ.get("FIREWORKS_API_KEY"):
        providers.append({"name": "fireworks", "has_key": True})

    # Groq
    if os.environ.get("GROQ_API_KEY"):
        providers.append({"name": "groq", "has_key": True})

    # Mistral
    if os.environ.get("MISTRAL_API_KEY"):
        providers.append({"name": "mistral", "has_key": True})

    # DeepSeek
    if os.environ.get("DEEPSEEK_API_KEY"):
        providers.append({"name": "deepseek", "has_key": True})

    # OpenRouter
    if os.environ.get("OPENROUTER_API_KEY"):
        providers.append({"name": "openrouter", "has_key": True})

    # Azure OpenAI
    if os.environ.get("AZURE_OPENAI_API_KEY") and os.environ.get("AZURE_OPENAI_ENDPOINT"):
        providers.append({"name": "azure_openai", "has_key": True, "endpoint": os.environ["AZURE_OPENAI_ENDPOINT"]})

    # Cerebras
    if os.environ.get("CEREBRAS_API_KEY"):
        providers.append({"name": "cerebras", "has_key": True})

    # Cloudflare Workers AI
    if os.environ.get("CLOUDFLARE_API_TOKEN"):
        providers.append({"name": "cloudflare", "has_key": True})

    return providers


def get_system_awareness() -> str:
    """Get complete system awareness: RAM, storage, VRAM, providers."""
    info = _get_system_info()
    ram = _get_ram_info()
    storage = _get_storage_info()
    vram = _get_vram_info()
    providers = _detect_providers()

    result = {
        "system": info,
        "ram": ram,
        "storage": storage,
        "vram": vram,
        "providers": providers,
        "provider_count": len(providers),
    }
    return json.dumps(result, indent=2)


def get_ram_status() -> str:
    ram = _get_ram_info()
    return json.dumps(ram, indent=2)


def get_storage_status() -> str:
    storage = _get_storage_info()
    return json.dumps(storage, indent=2)


def get_vram_status() -> str:
    vram = _get_vram_info()
    return json.dumps(vram, indent=2)


def detect_providers() -> str:
    providers = _detect_providers()
    return json.dumps({"providers": providers, "count": len(providers)}, indent=2)


# ---------------------------------------------------------------------------
# Tool definitions for registry
# ---------------------------------------------------------------------------

SYSTEM_AWARENESS_TOOL_DEFINITIONS: list[dict] = [
    {
        "name": "get_system_awareness",
        "description": "Get complete system awareness: RAM, storage, VRAM/GPU, detected API providers. Use this to understand hardware constraints before running heavy operations.",
        "func": get_system_awareness,
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "get_ram_status",
        "description": "Get current RAM status: total, available, used, percent. Use to check if system has enough memory for a task.",
        "func": get_ram_status,
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "get_storage_status",
        "description": "Get disk storage status for all mounted drives: total, free, used space.",
        "func": get_storage_status,
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "get_vram_status",
        "description": "Get GPU/VRAM status: GPU name, total VRAM, free VRAM, used VRAM. Detects NVIDIA, AMD, and other GPUs.",
        "func": get_vram_status,
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "detect_providers",
        "description": "Auto-detect available API providers from environment variables. Shows which providers have API keys configured.",
        "func": detect_providers,
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
]
