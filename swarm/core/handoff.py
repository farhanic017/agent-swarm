from __future__ import annotations
import json
from typing import Optional
from swarm.core.agent import Agent
from swarm.core.state import SharedState


HANDOFF_TOOL_SCHEMA = {
    "name": "transfer_to_agent",
    "description": "Transfer control to another specialized agent. Use when the current task requires expertise outside your domain. Provide all relevant context so the next agent can continue seamlessly.",
    "parameters": {
        "type": "object",
        "properties": {
            "agent": {
                "type": "string",
                "description": "The name of the agent to transfer to",
            },
            "context": {
                "type": "string",
                "description": "Summary of what has been done and what the next agent needs to do",
            },
        },
        "required": ["agent", "context"],
    },
}


def build_handoff_tools(agents: dict[str, Agent], current_agent: str) -> list:
    current = agents.get(current_agent)
    if not current:
        return []

    tool_defs = []
    for name, agent in agents.items():
        if name == current_agent:
            continue
        if current.handoff_targets and name not in current.handoff_targets:
            continue

        tool_defs.append({
            "type": "function",
            "function": {
                "name": f"transfer_to_{name.lower().replace(' ', '_')}",
                "description": f"Transfer to {name}. {agent.description}" if agent.description else f"Transfer to {name}",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "context": {
                            "type": "string",
                            "description": f"Summary of work done and instructions for {name}",
                        },
                    },
                    "required": ["context"],
                },
            },
        })

    return tool_defs


def parse_handoff(tool_calls: list, agents: dict[str, Agent]) -> Optional[tuple[str, str]]:
    for tc in tool_calls:
        func = tc.get("function", {})
        name = func.get("name", "")
        args_raw = func.get("arguments", "{}")
        if isinstance(args_raw, str):
            try:
                args = json.loads(args_raw)
            except json.JSONDecodeError:
                continue
        else:
            args = args_raw

        for agent_name in agents:
            expected = f"transfer_to_{agent_name.lower().replace(' ', '_')}"
            if name == expected:
                return agent_name, args.get("context", "")

        if name == "transfer_to_agent":
            return args.get("agent", ""), args.get("context", "")

    return None
