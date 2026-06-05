#!/usr/bin/env python3
"""
Example: Building a custom agent swarm from scratch.

This shows how to:
1. Define custom agents with specific roles
2. Set up handoff chains between them
3. Run the swarm with a complex task

Run: python examples/custom_swarm.py
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from swarm.config import SwarmConfig
from swarm.core.agent import Agent
from swarm.core.orchestrator import Orchestrator


async def main():
    config = SwarmConfig.from_opencode_config()
    orchestrator = Orchestrator(config=config)

    planner = Agent(
        name="planner",
        system_prompt="""You are a strategic planner. Break down complex requests 
into clear, actionable steps. Identify dependencies and order of operations.
Route to the right specialist agent when ready.""",
        description="Strategic planner that breaks down complex tasks",
        temperature=0.2,
        handoff_targets=["code_analyst", "writer"],
    )

    code_analyst = Agent(
        name="code_analyst",
        system_prompt="""You are a code analysis expert. Review code structure,
identify patterns, suggest improvements, and detect potential issues.
Use the read_file and run_python tools to analyze code.""",
        description="Analyzes code structure and patterns",
        tools=["read_file", "run_python", "list_directory"],
        temperature=0.2,
        handoff_targets=["planner"],
    )

    writer = Agent(
        name="writer",
        system_prompt="""You are a documentation specialist. Create clear,
comprehensive documentation and reports. Save them using write_file.""",
        description="Creates documentation and reports",
        tools=["write_file", "read_file"],
        temperature=0.4,
        handoff_targets=["planner"],
    )

    orchestrator.register_agents(planner, code_analyst, writer)

    prompt = "Analyze the agent-swarm project structure and write a summary report"
    if len(sys.argv) > 1:
        prompt = " ".join(sys.argv[1:])

    print(f"\nRunning custom swarm with prompt: {prompt}\n")
    state = await orchestrator.run(prompt, verbose=True)

    print(f"\n{'='*60}")
    print(f" FINAL RESULT")
    print(f"{'='*60}")
    if state.agent_turns:
        print(state.agent_turns[-1].output[:1500])


if __name__ == "__main__":
    asyncio.run(main())
