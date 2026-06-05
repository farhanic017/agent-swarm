from __future__ import annotations

from swarm.core.agent import Agent


def build_sub_agent_plan(agent: Agent, user_input: str, available_agents: dict[str, Agent]) -> list[dict]:
    """Create a deterministic helper plan for an agent.

    The actual execution still happens through the existing spawn_agent tool or
    SubAgentManager. This plan makes the capability explicit and visible in
    state/dashboard output before a model decides whether it needs helpers.
    """
    roles = [name for name in agent.sub_agent_roles if name in available_agents and name != agent.name]
    return [
        {
            "parent_agent": agent.name,
            "sub_agent": role,
            "task": _task_for_role(role, user_input),
            "model_preference": available_agents[role].model_preference,
            "pillar": available_agents[role].pillar,
        }
        for role in roles
    ]


def _task_for_role(role: str, user_input: str) -> str:
    if role == "testing":
        return f"Design and run edge-case tests for: {user_input}"
    if role == "security":
        return f"Audit security, privacy, and abuse risks for: {user_input}"
    if role == "analytics":
        return f"Find metrics, signals, and evidence for: {user_input}"
    if role == "legal":
        return f"Check legal, compliance, and policy risks for: {user_input}"
    if role == "ux_research":
        return f"Assess user needs, feedback, and usability risks for: {user_input}"
    if role == "finance":
        return f"Estimate cost, ROI, and financial risk for: {user_input}"
    if role == "design":
        return f"Evaluate product design and interaction implications for: {user_input}"
    if role == "reviewer":
        return f"Review final quality and release readiness for: {user_input}"
    return f"Support the parent agent on: {user_input}"
