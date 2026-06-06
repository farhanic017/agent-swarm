from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path


DENIED_SKILL_TERMS = (
    "steal",
    "exfiltrate",
    "credential",
    "password",
    "malware",
    "bypass",
    "disable security",
    "delete user files",
)


@dataclass(frozen=True)
class HermesSkillDraft:
    name: str
    trigger: str
    purpose: str
    steps: tuple[str, ...]
    evidence: tuple[str, ...] = ()
    version: int = 1
    confidence: int = 70
    tags: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "trigger": self.trigger,
            "purpose": self.purpose,
            "steps": list(self.steps),
            "evidence": list(self.evidence),
            "version": self.version,
            "confidence": self.confidence,
            "tags": list(self.tags),
        }


def propose_hermes_skill(task: str, outcome: str, lesson: str, agent_name: str = "hermes") -> dict:
    text = f"{task} {outcome} {lesson}".lower()
    name = _infer_skill_name(task, lesson)
    steps = _infer_steps(text)
    draft = HermesSkillDraft(
        name=name,
        trigger=_compact_sentence(task, 140),
        purpose=_compact_sentence(lesson or outcome or task, 220),
        steps=tuple(steps),
        evidence=tuple(item for item in (_compact_sentence(outcome, 180), _compact_sentence(lesson, 180)) if item),
        confidence=_confidence_score(task, outcome, lesson),
        tags=tuple(_infer_tags(text, agent_name)),
    )
    validation = validate_hermes_skill(draft.to_dict())
    return {"agent": agent_name, "draft": draft.to_dict(), "validation": validation}


def validate_hermes_skill(skill: dict) -> dict:
    name = str(skill.get("name", "")).strip()
    purpose = str(skill.get("purpose", "")).strip()
    steps = [str(step).strip() for step in skill.get("steps", []) if str(step).strip()]
    text = " ".join([name, purpose, " ".join(steps)]).lower()
    issues = []
    if not name:
        issues.append("skill name is required")
    if len(purpose) < 12:
        issues.append("purpose is too short")
    if len(steps) < 3:
        issues.append("at least three reusable steps are required")
    if any(term in text for term in DENIED_SKILL_TERMS):
        issues.append("unsafe or credential-related behavior is not allowed")
    if len(json.dumps(skill)) > 6000:
        issues.append("skill manifest is too large")
    return {
        "ok": not issues,
        "issues": issues,
        "gates": {
            "has_name": bool(name),
            "has_reusable_steps": len(steps) >= 3,
            "safe_terms": not any(term in text for term in DENIED_SKILL_TERMS),
            "bounded_size": len(json.dumps(skill)) <= 6000,
        },
    }


def persist_hermes_skill(skill: dict, root: str | Path = ".swarm_evolved_skills") -> dict:
    validation = validate_hermes_skill(skill)
    if not validation["ok"]:
        return {"saved": False, "validation": validation, "path": ""}
    base = Path(root)
    base.mkdir(parents=True, exist_ok=True)
    safe = _slug(str(skill["name"]))
    target = base / safe
    target.mkdir(parents=True, exist_ok=True)
    existing = sorted(target.glob("v*.json"))
    version = len(existing) + 1
    payload = dict(skill)
    payload["version"] = version
    payload["saved_at"] = time.time()
    payload["source"] = "hermes_self_evolution"
    manifest = target / f"v{version}.json"
    manifest.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    markdown = target / "SKILL.md"
    markdown.write_text(_format_skill_markdown(payload), encoding="utf-8")
    return {
        "saved": True,
        "validation": validation,
        "path": str(manifest),
        "skill_dir": str(target),
        "version": version,
        "load_policy": "reviewed evolved skills can be injected into future Hermes prompts or temporary skill sessions",
    }


def list_hermes_skills(root: str | Path = ".swarm_evolved_skills") -> list[dict]:
    base = Path(root)
    if not base.exists():
        return []
    result = []
    for manifest in sorted(base.glob("*/v*.json")):
        try:
            data = json.loads(manifest.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        result.append(
            {
                "name": data.get("name", manifest.parent.name),
                "version": data.get("version", 0),
                "path": str(manifest),
                "purpose": data.get("purpose", ""),
                "tags": data.get("tags", []),
            }
        )
    return result


def build_hermes_evolution_plan(task: str, current_skills: list[str] | None = None) -> dict:
    skills = current_skills or []
    return {
        "agent": "hermes",
        "task": task,
        "current_skills": skills,
        "evolution_loop": [
            "observe successful work, failures, and repeated workflows",
            "compress the reusable pattern into a candidate skill",
            "validate safety, scope, and reuse gates",
            "save a versioned manifest and SKILL.md only after validation",
            "reuse the skill in future prompts when tags match the new task",
        ],
        "guardrails": {
            "no_unreviewed_code_execution": True,
            "no_secret_or_credential_skills": True,
            "version_every_skill": True,
            "keep_skills_small_and_task_scoped": True,
            "master_review_before_release_use": True,
        },
    }


def _infer_skill_name(task: str, lesson: str) -> str:
    source = lesson or task or "hermes evolved skill"
    words = [word.strip(".,:;!?()[]{}").lower() for word in source.split()]
    useful = [word for word in words if len(word) > 3 and word not in {"always", "should", "with", "from", "into", "using"}]
    return " ".join(useful[:5]).title() or "Hermes Evolved Skill"


def _infer_steps(text: str) -> list[str]:
    steps = ["identify when the pattern applies", "execute the proven workflow", "validate the result before handoff"]
    if "test" in text or "bug" in text:
        steps.insert(2, "add regression tests for the discovered edge case")
    if "design" in text or "visual" in text:
        steps.insert(1, "capture visual constraints and acceptance criteria")
    if "api" in text or "backend" in text:
        steps.insert(1, "define inputs, outputs, permissions, and failure modes")
    return steps


def _infer_tags(text: str, agent_name: str) -> list[str]:
    tags = ["hermes", "self-evolved", agent_name]
    for token in ("testing", "design", "backend", "frontend", "security", "browser", "animation", "vision", "job", "scraper"):
        if token in text:
            tags.append(token)
    if "test" in text:
        tags.append("testing")
    return sorted(set(tags))


def _confidence_score(task: str, outcome: str, lesson: str) -> int:
    score = 62
    if outcome:
        score += 10
    if lesson:
        score += 12
    if any(token in outcome.lower() for token in ("passed", "success", "fixed", "verified")):
        score += 10
    return min(96, score)


def _compact_sentence(value: str, limit: int) -> str:
    value = " ".join(str(value or "").split())
    return value[:limit]


def _slug(value: str) -> str:
    safe = "".join(ch.lower() if ch.isalnum() else "-" for ch in value)
    while "--" in safe:
        safe = safe.replace("--", "-")
    return safe.strip("-") or "hermes-skill"


def _format_skill_markdown(skill: dict) -> str:
    steps = "\n".join(f"{idx + 1}. {step}" for idx, step in enumerate(skill.get("steps", [])))
    tags = ", ".join(skill.get("tags", []))
    return (
        f"# {skill.get('name', 'Hermes Evolved Skill')}\n\n"
        f"Version: {skill.get('version', 1)}\n\n"
        f"Purpose: {skill.get('purpose', '')}\n\n"
        f"Trigger: {skill.get('trigger', '')}\n\n"
        f"Tags: {tags}\n\n"
        f"## Workflow\n\n{steps}\n"
    )
