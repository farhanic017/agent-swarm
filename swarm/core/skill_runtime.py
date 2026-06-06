from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class TemporarySkillSession:
    root: Path
    installed: list[Path] = field(default_factory=list)

    def install_manifest(self, skill_name: str, source: str = "catalog") -> dict:
        safe = "".join(ch for ch in skill_name.lower() if ch.isalnum() or ch in ("-", "_")).strip("-_")
        if not safe:
            raise ValueError("skill_name is required")
        target = self.root / safe
        target.mkdir(parents=True, exist_ok=True)
        manifest = target / "SKILL.md"
        manifest.write_text(
            f"# {skill_name}\n\nTemporary skill acquired from {source} for this swarm run.\n",
            encoding="utf-8",
        )
        self.installed.append(target)
        return {"skill": skill_name, "source": source, "path": str(target), "temporary": True}

    def cleanup(self) -> dict:
        removed = []
        for path in list(self.installed):
            if path.exists() and self.root in path.parents:
                shutil.rmtree(path, ignore_errors=True)
                removed.append(str(path))
        self.installed.clear()
        if self.root.exists():
            try:
                self.root.rmdir()
            except OSError:
                pass
        return {"removed": removed, "remaining": len(self.installed)}


def create_temporary_skill_session(root: str | Path = ".swarm_tmp_skills") -> TemporarySkillSession:
    path = Path(root)
    path.mkdir(parents=True, exist_ok=True)
    return TemporarySkillSession(root=path)


def plan_required_skills(task: str, existing_skills: list[str] | None = None) -> dict:
    existing = {skill.lower() for skill in (existing_skills or [])}
    task_lower = task.lower()
    wanted = []
    mapping = {
        "browser": "browser",
        "figma": "figma-control",
        "video": "video-editing",
        "photo": "photo-editing",
        "image": "image-generation",
        "blender": "blender-automation",
        "security": "security-review",
        "performance": "performance-profiling",
        "mcp": "mcp-integration",
    }
    for token, skill in mapping.items():
        if token in task_lower and skill not in existing:
            wanted.append(skill)
    return {
        "required": wanted,
        "existing": sorted(existing),
        "temporary_install": bool(wanted),
        "cleanup_policy": "delete temporary skills after all agents finish",
    }
