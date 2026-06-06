from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
import re


@dataclass
class Skill:
    name: str
    description: str
    content: str
    source: str
    triggers: list = field(default_factory=list)
    file_type: str = "document"
    source_url: Optional[str] = None
    author: Optional[str] = None


_YAML_FRONT_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n?(.*)", re.DOTALL)


def parse_skill_md(path: str) -> Optional[Skill]:
    try:
        raw = Path(path).read_text(encoding="utf-8")
    except Exception:
        return None

    m = _YAML_FRONT_RE.match(raw)
    if not m:
        return None

    front_raw = m.group(1)
    body = m.group(2).strip()

    front = _parse_simple_yaml(front_raw)
    name = front.get("name") or _filename_to_name(path)
    description = front.get("description") or ""
    triggers_raw = front.get("triggers") or front.get("tags") or []
    if isinstance(triggers_raw, str):
        triggers = [t.strip() for t in triggers_raw.split(",")]
    elif isinstance(triggers_raw, list):
        triggers = [str(t).strip() for t in triggers_raw if t]
    else:
        triggers = []
    source_url = front.get("source_url") or front.get("url")

    return Skill(
        name=str(name),
        description=str(description),
        content=body,
        source=path,
        triggers=triggers,
        file_type=front.get("file_type", "document"),
        source_url=source_url,
        author=front.get("author"),
    )


def _filename_to_name(path: str) -> str:
    import os
    base = os.path.splitext(os.path.basename(path))[0]
    base = base.replace("-", " ").replace("_", " ")
    return base.title()


def _parse_simple_yaml(text: str) -> dict:
    result = {}
    current_key = None
    current_list = None
    for line in text.split("\n"):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("- "):
            item = stripped[2:].strip().strip('"').strip("'")
            if current_list is not None:
                current_list.append(item)
            continue

        current_list = None
        if ":" in stripped:
            key, _, val = stripped.partition(":")
            current_key = key.strip()
            val = val.strip()
            if val == "":
                current_list = []
                result[current_key] = current_list
            else:
                result[current_key] = val.strip('"').strip("'")
    return result
