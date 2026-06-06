from __future__ import annotations

from datetime import datetime, timezone


def build_obsidian_note(title: str, body: str, tags: list[str] | None = None, links: list[str] | None = None) -> str:
    clean_tags = [_slug(tag) for tag in (tags or []) if tag.strip()]
    clean_links = [link.strip() for link in (links or []) if link.strip()]
    frontmatter = [
        "---",
        f"title: {title}",
        f"created: {datetime.now(timezone.utc).replace(microsecond=0).isoformat()}",
        f"tags: [{', '.join(clean_tags)}]",
        "---",
        "",
    ]
    link_block = ""
    if clean_links:
        link_lines = ["## Links", ""]
        link_lines.extend(f"- [[{link}]]" for link in clean_links)
        link_block = "\n" + "\n".join(link_lines) + "\n"
    return "\n".join(frontmatter) + f"# {title}\n\n{body.strip()}\n" + link_block


def plan_obsidian_vault(project: str, topics: list[str] | None = None) -> dict:
    topic_list = [topic.strip() for topic in (topics or []) if topic.strip()]
    if not topic_list:
        topic_list = ["Architecture", "Agent Decisions", "Security Review", "Test Evidence"]
    notes = []
    for topic in topic_list:
        notes.append(
            {
                "title": topic,
                "path": f"{_slug(topic)}.md",
                "tags": ["agent-swarm", _slug(project), _slug(topic)],
                "links": [other for other in topic_list if other != topic][:3],
            }
        )
    return {
        "app": "Obsidian",
        "project": project,
        "vault_policy": "Create markdown notes only inside the configured allowed project root.",
        "notes": notes,
        "graph_view": {
            "center": topic_list[0],
            "clusters": ["architecture", "decisions", "security", "tests"],
            "backlinks_enabled": True,
        },
    }


def _slug(value: str) -> str:
    cleaned = "".join(ch.lower() if ch.isalnum() else "-" for ch in value.strip())
    while "--" in cleaned:
        cleaned = cleaned.replace("--", "-")
    return cleaned.strip("-") or "note"
