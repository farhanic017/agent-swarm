"""Continuous Learning System — agents learn from experience.

Agents log lessons from their work: what worked, what didn't, patterns
discovered, and errors avoided. Lessons are scored by relevance and
injected into system prompts so agents get smarter over time.

Lessons persist across sessions via a JSON file, building an ever-growing
knowledge base that makes the swarm more efficient with each run.
"""

from __future__ import annotations
import json
import os
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class Lesson:
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    agent_name: str = ""
    context: str = ""
    outcome: str = ""
    lesson: str = ""
    tags: list = field(default_factory=list)
    success: bool = True
    score: int = 1
    timestamp: float = field(default_factory=time.time)
    apply_count: int = 0

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "agent_name": self.agent_name,
            "context": self.context[:200],
            "outcome": self.outcome[:200],
            "lesson": self.lesson[:500],
            "tags": self.tags,
            "success": self.success,
            "score": self.score,
            "timestamp": self.timestamp,
            "apply_count": self.apply_count,
        }


class LessonLearner:
    """Manages the continuous learning system for agents.

    Lessons are stored in a JSON file and loaded on initialization.
    Relevance scoring uses keyword overlap between lesson tags/context
    and the current task. Top lessons are injected into agent prompts.
    """

    def __init__(self, storage_path: str = ""):
        self._lessons: list[Lesson] = []
        self._max_lessons: int = 2000
        self._max_inject: int = 5
        self._storage_path = storage_path or os.path.join(
            os.getcwd(), ".swarm_lessons.json"
        )
        self._load()

    def log_lesson(self, agent_name: str, context: str,
                   outcome: str, lesson: str,
                   tags: list = None, success: bool = True) -> Lesson:
        """Log a new lesson learned by an agent."""
        lsn = Lesson(
            agent_name=agent_name,
            context=context,
            outcome=outcome,
            lesson=lesson,
            tags=tags or [],
            success=success,
        )
        self._lessons.append(lsn)
        if len(self._lessons) > self._max_lessons:
            self._lessons = self._lessons[-self._max_lessons:]
        self._save()
        return lsn

    def get_relevant_lessons(self, agent_name: str,
                             current_context: str,
                             max_results: int = 0) -> list[Lesson]:
        """Score and return the most relevant lessons for a given context."""
        max_results = max_results or self._max_inject
        context_lower = current_context.lower()
        context_words = set(context_lower.split())

        scored = []
        for lsn in self._lessons:
            if lsn.agent_name != agent_name and lsn.agent_name != "*":
                continue
            score = self._score_relevance(lsn, context_words)
            if score > 0:
                scored.append((score, lsn))

        scored.sort(key=lambda x: x[0], reverse=True)
        result = [lsn for _, lsn in scored[:max_results]]
        for lsn in result:
            lsn.apply_count += 1
        self._save()
        return result

    def _score_relevance(self, lsn: Lesson, context_words: set) -> int:
        score = 0
        lesson_text = (lsn.context + " " + " ".join(lsn.tags)).lower()
        lesson_words = set(lesson_text.split())
        overlap = context_words & lesson_words
        score += len(overlap) * 2
        for word in context_words:
            for lw in lesson_words:
                if len(word) > 3 and len(lw) > 3 and (word in lw or lw in word):
                    score += 1
        if score == 0 and lsn.success:
            return 0
        if not lsn.success:
            score += 3
        score += min(lsn.apply_count, 5)
        return score

    def get_lessons_for_prompt(self, agent_name: str,
                               current_context: str,
                               max_results: int = 0) -> str:
        """Get a formatted string of relevant lessons for prompt injection."""
        lessons = self.get_relevant_lessons(agent_name, current_context, max_results)
        if not lessons:
            return ""
        lines = ["=== Lessons Learned (from experience) ==="]
        for lsn in lessons:
            tag_str = f"[{', '.join(lsn.tags)}]" if lsn.tags else ""
            lines.append(
                f"- {lsn.lesson[:200]} "
                f"(context: {lsn.context[:50]}... "
                f"applied {lsn.apply_count}x) {tag_str}"
            )
        return "\n".join(lines)

    def get_stats(self) -> dict:
        total = len(self._lessons)
        by_agent = {}
        successes = 0
        for lsn in self._lessons:
            by_agent[lsn.agent_name] = by_agent.get(lsn.agent_name, 0) + 1
            if lsn.success:
                successes += 1
        return {
            "total_lessons": total,
            "by_agent": by_agent,
            "success_rate": successes / total if total > 0 else 0,
            "total_applies": sum(l.apply_count for l in self._lessons),
        }

    def prune_low_value(self, min_score: int = 2):
        """Remove lessons with low relevance scores to keep the store lean."""
        before = len(self._lessons)
        self._lessons = [l for l in self._lessons if l.score >= min_score]
        self._save()
        return before - len(self._lessons)

    def _save(self):
        try:
            data = {
                "lessons": [l.to_dict() for l in self._lessons],
                "updated_at": time.time(),
            }
            Path(self._storage_path).write_text(
                json.dumps(data, indent=2), encoding="utf-8"
            )
        except (OSError, IOError):
            pass

    def _load(self):
        try:
            path = Path(self._storage_path)
            if path.exists():
                data = json.loads(path.read_text(encoding="utf-8"))
                for item in data.get("lessons", []):
                    self._lessons.append(Lesson(**item))
        except (json.JSONDecodeError, OSError, IOError):
            pass
