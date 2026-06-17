from __future__ import annotations
import json
import time
from dataclasses import dataclass, field
from typing import Optional
from pathlib import Path


@dataclass
class AgentTurn:
    agent_name: str
    input: str
    output: str
    model: str
    tokens_used: int = 0
    duration_ms: int = 0
    tool_calls: list = field(default_factory=list)


@dataclass
class SharedState:
    user_input: str = ""
    conversation_history: list = field(default_factory=list)
    agent_turns: list = field(default_factory=list)
    artifacts: dict = field(default_factory=dict)
    metadata: dict = field(default_factory=dict)
    current_agent: str = ""
    summary: str = ""
    iteration: int = 0

    def add_turn(self, turn: AgentTurn):
        self.agent_turns.append(turn)
        self.iteration += 1

    def to_context_string(self) -> str:
        parts = [f"Original request: {self.user_input}"]
        if self.summary:
            parts.append(f"Progress so far: {self.summary}")
        if self.artifacts:
            parts.append(f"Artifacts: {json.dumps(self.artifacts, indent=2)}")
        return "\n\n".join(parts)

    def set_artifact(self, key: str, value: any):
        self.artifacts[key] = value

    def get_artifact(self, key: str, default=None):
        return self.artifacts.get(key, default)

    def save(self, path: str):
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "user_input": self.user_input,
            "summary": self.summary,
            "artifacts": self.artifacts,
            "metadata": self.metadata,
            "iteration": self.iteration,
            "agent_turns": [
                {
                    "agent_name": t.agent_name,
                    "input": t.input[:500],
                    "output": t.output[:500],
                    "model": t.model,
                    "tokens_used": t.tokens_used,
                    "duration_ms": t.duration_ms,
                }
                for t in self.agent_turns
            ],
        }
        p.write_text(json.dumps(data, indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: str) -> SharedState:
        p = Path(path)
        if not p.exists():
            return cls()
        data = json.loads(p.read_text(encoding="utf-8"))
        state = cls(
            user_input=data.get("user_input", ""),
            summary=data.get("summary", ""),
            artifacts=data.get("artifacts", {}),
            metadata=data.get("metadata", {}),
            iteration=data.get("iteration", 0),
        )
        state.agent_turns = [
            AgentTurn(**t) for t in data.get("agent_turns", [])
        ]
        return state
