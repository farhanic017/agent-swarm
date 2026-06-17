from __future__ import annotations
import asyncio
import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, Callable

from swarm.skills.models import Skill, parse_skill_md


# Root-level skill file names (universal, not platform-specific)
ROOT_SKILL_FILES = [
    "SKILL.md",
    "AGENTS.md",
    "CLAUDE.md",
    "CLINE.md",
    ".cursorrules",
]

# All standard platform skill locations: (user_dir, project_dir)
# user_dir uses ~/ expansion; project_dir is relative to project root
_KNOWN_PLATFORMS: dict[str, tuple[str | None, str | None]] = {}


def register_platform(
    name: str,
    user_dir: str | None = None,
    project_dir: str | None = None,
):
    """Register a platform's skill directories for discovery.

    Args:
        name: Platform name (e.g. 'vscode', 'antigravity')
        user_dir: User-global skill directory (supports ~/ expansion)
        project_dir: Project-local skill directory (relative to project root)

    Future-proof: any platform name follows the convention
    ``~/.{name}/skills/`` (user) and ``.{name}/skills/`` (project)
    automatically — only call this to override conventions.
    """
    _KNOWN_PLATFORMS[name] = (user_dir, project_dir)


# ---- Register all known platforms ----

# Claude Code
register_platform("claude", "~/.claude/skills", ".claude/skills")
# OpenCode
register_platform("opencode", "~/.config/opencode/skills", ".opencode/skills")
# Gemini CLI
register_platform("gemini", "~/.gemini/skills", ".gemini/skills")
# OpenAI Codex CLI
register_platform("codex", "~/.codex/skills", ".codex/skills")
# Cursor
register_platform("cursor", "~/.cursor/rules", ".cursor/rules")
# Windsurf
register_platform("windsurf", "~/.windsurf/skills", ".windsurf/skills")
# Generic agents directory
register_platform("agents", "~/.agents/skills", ".agents/skills")

# VS Code / VS Studio Code (via Continue.dev, Cline, Copilot extensions)
register_platform("vscode", "~/.vscode/skills", ".vscode")
register_platform("continue", "~/.continue", ".continue")
register_platform("copilot", None, ".github")

# Antigravity 1.x / 2.x
register_platform("antigravity", "~/.antigravity/skills", ".antigravity/skills")

# Aider
register_platform("aider", "~/.aider/skills", ".aider/skills")

# Cline
register_platform("cline", "~/.cline/skills", ".cline")

# OpenClaw
register_platform("openclaw", "~/.openclaw/skills", ".openclaw/skills")

# Windsurf Cascade
register_platform("cascade", None, ".cascade/skills")


# ---- Custom source registration ----

_custom_source_fns: list[Callable[[], list[Skill]]] = []


def add_custom_source(fn: Callable[[], list[Skill]]):
    """Register a custom skill source function.

    The function should return a list of Skill objects. Called during
    every full discovery cycle.
    """
    _custom_source_fns.append(fn)


# ---- Internal helpers ----

def _expand_home(path: str) -> str:
    return os.path.expanduser(path)


def _scan_directory(dir_path: str, recursive: bool = True) -> list[Skill]:
    skills = []
    resolved = Path(dir_path)
    if not resolved.exists() or not resolved.is_dir():
        return skills

    pattern = "**/*.md" if recursive else "*.md"
    for md_file in resolved.glob(pattern):
        skill = parse_skill_md(str(md_file))
        if skill:
            skills.append(skill)
    return skills


def _convention_user_dir(name: str) -> str:
    """Convention: ~/.{name}/skills/ for user-global skills."""
    return f"~/.{name}/skills"


def _convention_project_dir(name: str) -> str:
    """Convention: .{name}/skills/ for project-local skills."""
    return f".{name}/skills"


# ---- Discovery API ----

def discover_from_registered_platforms() -> list[Skill]:
    """Scan user-global skill dirs for all registered platforms."""
    skills = []

    for name, (user_dir, _) in _KNOWN_PLATFORMS.items():
        paths_to_try = []

        if user_dir is not None:
            paths_to_try.append(_expand_home(user_dir))

        # Also try convention path unless it's already registered
        convention = _convention_user_dir(name)
        expanded = _expand_home(convention)
        if expanded not in paths_to_try:
            paths_to_try.append(expanded)

        for path in paths_to_try:
            found = _scan_directory(path)
            skills.extend(found)

    return skills


def discover_project_skills(project_root: Optional[str] = None) -> list[Skill]:
    """Scan project-level skill dirs for all registered platforms + root files."""
    skills = []
    if not project_root:
        project_root = os.getcwd()

    root = Path(project_root)

    for name, (_, project_dir) in _KNOWN_PLATFORMS.items():
        paths_to_try = []

        if project_dir is not None:
            paths_to_try.append(str(root / project_dir))

        # Also try convention path unless it's already registered
        convention = str(root / _convention_project_dir(name))
        if convention not in paths_to_try:
            paths_to_try.append(convention)

        for path in paths_to_try:
            found = _scan_directory(path)
            skills.extend(found)

    for fname in ROOT_SKILL_FILES:
        target = root / fname
        if target.exists() and target.is_file():
            skill = parse_skill_md(str(target))
            if skill:
                skills.append(skill)

    return skills


async def discover_from_skills_sh(timeout: float = 5.0) -> list[Skill]:
    """Fetch top skills from Vercel's skills.sh registry."""
    skills = []
    try:
        import urllib.request
        import json

        def _fetch():
            req = urllib.request.Request(
                "https://skills.sh/api/skills/top",
                headers={"User-Agent": "agent-swarm/1.0"},
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode())

        data = await asyncio.to_thread(_fetch)
        items = data if isinstance(data, list) else data.get("skills", [])
        for item in items[:20]:
            name = item.get("name", "unknown")
            description = item.get("description", "")
            skills.append(Skill(
                name=name,
                description=description,
                content=item.get("readme", description),
                source=f"skills.sh/{name}",
                triggers=item.get("keywords", []) or item.get("tags", []),
                source_url=item.get("url") or f"https://skills.sh/{name}",
                author=item.get("author"),
            ))
    except Exception:
        pass
    return skills


def discover_from_custom_sources() -> list[Skill]:
    """Invoke all registered custom source functions."""
    skills = []
    for fn in _custom_source_fns:
        try:
            result = fn()
            skills.extend(result)
        except Exception:
            pass
    return skills


def discover_all_skills(project_root: Optional[str] = None) -> list[Skill]:
    """Full discovery: registered platforms + conventions + project + customs."""
    skills = []
    skills.extend(discover_from_registered_platforms())
    skills.extend(discover_project_skills(project_root))
    skills.extend(discover_from_custom_sources())
    return skills


def list_registered_platforms() -> dict[str, tuple[str | None, str | None]]:
    """Return a copy of the platform registry for inspection."""
    return dict(_KNOWN_PLATFORMS)


# Backward compatibility alias
discover_local_skills = discover_from_registered_platforms
