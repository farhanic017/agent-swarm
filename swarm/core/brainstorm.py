"""Collaborative Brainstorm Protocol — multi-agent problem solving.

When a task exceeds a complexity threshold, the system triggers a
brainstorm session where all registered agents contribute perspectives,
then collaboratively define a plan and assign work packages.
"""

from __future__ import annotations
import asyncio
import json
import time
import uuid
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class BrainstormIdea:
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    agent_name: str = ""
    perspective: str = ""
    idea: str = ""
    confidence: float = 0.5
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "agent_name": self.agent_name,
            "perspective": self.perspective,
            "idea": self.idea[:500],
            "confidence": self.confidence,
            "timestamp": self.timestamp,
        }


@dataclass
class BrainstormSession:
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    problem: str = ""
    context: str = ""
    status: str = "open"
    ideas: list = field(default_factory=list)
    plan: str = ""
    work_packages: list = field(default_factory=list)
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "problem": self.problem[:200],
            "status": self.status,
            "ideas_count": len(self.ideas),
            "plan": self.plan[:500],
            "work_packages": self.work_packages,
            "created_at": self.created_at,
        }


COMPLEXITY_KEYWORDS = [
    "complex", "complicated", "difficult", "challenging", "large",
    "multi-step", "multi component", "full stack", "end to end",
    "architecture", "design", "architect", "multiple files",
    "refactor", "redesign", "overhaul", "migration",
    "integrate", "multiple services", "distributed",
]

COMPLEXITY_THRESHOLD = 3


def estimate_complexity(task_description: str) -> int:
    """Estimate task complexity by keyword matching.

    Returns an integer score. A score >= COMPLEXITY_THRESHOLD
    triggers a collaborative brainstorm.
    """
    desc = task_description.lower()
    score = 0
    for kw in COMPLEXITY_KEYWORDS:
        if kw in desc:
            score += 1
    return score


class BrainstormEngine:
    """Manages brainstorming sessions where agents collaborate on complex problems."""

    def __init__(self):
        self._sessions: dict[str, BrainstormSession] = {}
        self._max_sessions: int = 100
        self._complexity_threshold: int = COMPLEXITY_THRESHOLD

    @property
    def complexity_threshold(self) -> int:
        return self._complexity_threshold

    @complexity_threshold.setter
    def complexity_threshold(self, value: int):
        self._complexity_threshold = max(1, value)

    def create_session(self, problem: str, context: str = "") -> BrainstormSession:
        session = BrainstormSession(problem=problem, context=context)
        self._sessions[session.id] = session
        if len(self._sessions) > self._max_sessions:
            oldest = min(self._sessions.keys(),
                         key=lambda k: self._sessions[k].created_at)
            del self._sessions[oldest]
        return session

    def add_idea(self, session_id: str, agent_name: str,
                 perspective: str, idea: str,
                 confidence: float = 0.5) -> Optional[BrainstormIdea]:
        session = self._sessions.get(session_id)
        if not session or session.status != "open":
            return None
        bf = BrainstormIdea(
            agent_name=agent_name,
            perspective=perspective,
            idea=idea,
            confidence=confidence,
        )
        session.ideas.append(bf)
        return bf

    def finalize(self, session_id: str, plan: str,
                 work_packages: list[str] = None) -> bool:
        session = self._sessions.get(session_id)
        if not session:
            return False
        session.status = "planned"
        session.plan = plan
        session.work_packages = work_packages or []
        return True

    def get_session(self, session_id: str) -> Optional[BrainstormSession]:
        return self._sessions.get(session_id)

    def get_active_session(self) -> Optional[BrainstormSession]:
        for s in self._sessions.values():
            if s.status == "open":
                return s
        return None

    def get_session_summary(self, session_id: str) -> str:
        session = self._sessions.get(session_id)
        if not session:
            return "Session not found."
        lines = [
            f"=== Brainstorm: {session.problem[:100]} ===",
            f"Status: {session.status}",
            f"Ideas ({len(session.ideas)}):",
        ]
        for idea in session.ideas:
            lines.append(
                f"  [{idea.agent_name}] ({idea.perspective}, confidence={idea.confidence:.1f}): {idea.idea[:200]}"
            )
        if session.plan:
            lines.append(f"Plan: {session.plan[:300]}")
        if session.work_packages:
            lines.append("Work Packages:")
            for wp in session.work_packages:
                lines.append(f"  - {wp[:150]}")
        return "\n".join(lines)

    def should_brainstorm(self, task: str) -> bool:
        return estimate_complexity(task) >= self._complexity_threshold

    def to_dict(self) -> dict:
        sessions = list(self._sessions.values())[-5:]
        return {
            "active_sessions": len(self._sessions),
            "sessions": [s.to_dict() for s in sessions],
        }
