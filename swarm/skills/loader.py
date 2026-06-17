from __future__ import annotations
import re
from typing import Optional

from swarm.skills.models import Skill
from swarm.skills.sources import discover_all_skills, discover_from_skills_sh


_STOP_WORDS = frozenset({
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "shall", "can", "need", "dare", "ought",
    "used", "to", "of", "in", "for", "on", "with", "at", "by", "from",
    "as", "into", "through", "during", "before", "after", "above", "below",
    "between", "out", "off", "over", "under", "again", "further", "then",
    "once", "here", "there", "when", "where", "why", "how", "all", "each",
    "every", "both", "few", "more", "most", "other", "some", "such", "no",
    "nor", "not", "only", "own", "same", "so", "than", "too", "very",
    "just", "because", "but", "and", "or", "if", "while", "that", "this",
    "these", "those", "it", "its", "what", "which", "who", "whom",
    "about", "up", "down", "like", "also", "any", "get", "make", "use",
    "tell", "give", "take", "put", "let", "try", "ask", "need", "want",
    "please", "help", "doing", "done", "going", "know", "think", "see",
    "looking", "looking", "want", "work", "using", "used", "based",
})


def _extract_keywords(text: str) -> set[str]:
    text = text.lower()
    words = re.findall(r"[a-zA-Z_][a-zA-Z0-9_]{2,}", text)
    return {w for w in words if w not in _STOP_WORDS and not w.isdigit()}


def _score_skill(skill: Skill, keywords: set[str]) -> float:
    if not keywords:
        return 0.0

    score = 0.0
    name_lower = skill.name.lower()
    desc_lower = skill.description.lower()

    for kw in keywords:
        if kw in name_lower:
            score += 3.0
        if kw in desc_lower:
            score += 1.0
        for trigger in skill.triggers:
            if kw in trigger.lower():
                score += 2.0

    # Boost for exact trigger matches
    for trigger in skill.triggers:
        trigger_lower = trigger.lower()
        if trigger_lower in keywords:
            score += 2.5

    return score / max(len(keywords), 1)


class SkillLoader:
    def __init__(self):
        self._all_skills: list[Skill] = []
        self._discovered = False
        self._web_indexed = False

    def discover(self, project_root: str = None):
        self._all_skills = discover_all_skills(project_root)
        self._discovered = True

    async def discover_web(self):
        if self._web_indexed:
            return
        web_skills = await discover_from_skills_sh()
        existing = {s.name for s in self._all_skills}
        for s in web_skills:
            if s.name not in existing:
                self._all_skills.append(s)
        self._web_indexed = True

    def match_skills(self, task: str, max_skills: int = 3, min_score: float = 0.5) -> list[Skill]:
        if not self._discovered:
            self.discover()

        keywords = _extract_keywords(task)
        if not keywords:
            return []

        scored = [(s, _score_skill(s, keywords)) for s in self._all_skills]
        scored.sort(key=lambda x: x[1], reverse=True)

        matched = [s for s, sc in scored if sc >= min_score][:max_skills]

        return matched

    def format_skills_block(self, skills: list[Skill]) -> str:
        if not skills:
            return ""

        parts = ["<injected_skills>"]
        parts.append("The following specialized skills are active for this task:\n")
        for i, skill in enumerate(skills, 1):
            parts.append(f"## {i}. {skill.name}")
            parts.append(f"   {skill.description}")
            parts.append(f"   [source: {skill.source}]\n")
            parts.append(skill.content)
            parts.append("")
        parts.append("</injected_skills>")
        return "\n".join(parts)

    def get_injected_prompt(self, agent, task: str) -> str:
        matched = self.match_skills(task)
        if not matched:
            return agent.system_prompt

        skill_block = self.format_skills_block(matched)
        return f"{skill_block}\n\n{agent.system_prompt}"

    def count(self) -> int:
        return len(self._all_skills)

    def get_stats(self) -> dict:
        return {
            "total_skills": len(self._all_skills),
            "local": sum(1 for s in self._all_skills if not s.source.startswith("skills.sh")),
            "web": sum(1 for s in self._all_skills if s.source.startswith("skills.sh")),
        }
