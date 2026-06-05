from __future__ import annotations
from dataclasses import dataclass, field
from typing import Callable, Optional


@dataclass
class Agent:
    name: str
    system_prompt: str
    model: Optional[str] = None
    temperature: float = 0.3
    max_tokens: int = 4096
    tools: list = field(default_factory=list)
    handoff_targets: list = field(default_factory=list)
    description: str = ""
    task_type: str = "general"
    pillar: str = "act"
    category: str = "general"
    model_preference: str = "auto"
    sub_agent_roles: list = field(default_factory=list)

    def can_handoff_to(self, agent_name: str) -> bool:
        return agent_name in self.handoff_targets or not self.handoff_targets


AGENT_TASK_MAP = {
    "triage": "general",
    "researcher": "reasoning",
    "coder": "coding",
    "writer": "chat",
    "text_editor": "chat",
    "prompt_generator": "chat",
    "reviewer": "coding",
    "security": "coding",
    "testing": "coding",
    "debugging": "coding",
    "marketing": "chat",
    "finance": "reasoning",
    "analytics": "reasoning",
    "trading": "reasoning",
    "legal": "reasoning",
    "ux_research": "reasoning",
    "localization": "chat",
    "product_manager": "reasoning",
    "sales": "chat",
    "design": "chat",
    "photo_editor": "vision",
    "video_editor": "vision",
    "figma_controller": "vision",
    "council_master": "reasoning",
}


def resolve_task_type(agent: Agent) -> str:
    if agent.task_type and agent.task_type != "general":
        return agent.task_type
    return AGENT_TASK_MAP.get(agent.name, "general")


HandoffFunction = Callable[[str], Optional[str]]
