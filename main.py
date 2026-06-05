#!/usr/bin/env python3
"""
Agent Swarm — Multi-Agent Orchestration Framework

A production-grade framework for building and running swarms of specialized
AI agents that collaborate to solve complex tasks.

Usage:
  python main.py [options]

Examples:
  python main.py                          # Interactive mode
  python main.py "Write a Python script to sort a list"
  python main.py --headless "Research AI agents and write a report"
  python main.py --list-agents
  python main.py --config path/to/config.json
"""

import asyncio
import json
import os
import sys
from pathlib import Path

from swarm.config import SwarmConfig
from swarm.core.agent import Agent
from swarm.core.orchestrator import Orchestrator
from swarm.core.state import SharedState
from swarm.agents.catalog import AGENT_SPECS, create_specialist_agents, summarize_catalog
from swarm.core.ab_testing import run_ab_test
from swarm.core.council import run_council_vote
from swarm.core.dashboard import write_dashboard
from swarm.core.provider_assignment import assign_distinct_provider_models


def load_custom_agents(path: str) -> list[Agent]:
    agents = []
    p = Path(path)
    if not p.exists():
        return agents
    data = json.loads(p.read_text(encoding="utf-8"))
    for entry in data:
        agent = Agent(
            name=entry.get("name", "unnamed"),
            system_prompt=entry.get("system_prompt", ""),
            model=entry.get("model"),
            temperature=entry.get("temperature", 0.3),
            max_tokens=entry.get("max_tokens", 4096),
            tools=entry.get("tools", []),
            handoff_targets=entry.get("handoff_targets", []),
            description=entry.get("description", ""),
            task_type=entry.get("task_type", "general"),
            pillar=entry.get("pillar", "act"),
            category=entry.get("category", "general"),
            model_preference=entry.get("model_preference", "auto"),
            sub_agent_roles=entry.get("sub_agent_roles", []),
        )
        agents.append(agent)
    return agents


def build_default_swarm() -> Orchestrator:
    config = SwarmConfig.from_opencode_config()

    print(f"[config] Detected providers: {list(config.providers.keys())}")
    if config.providers:
        best = config.get_best_model()
        cheap = config.get_cheapest_model()
        print(f"[config] Best model: {best}")
        print(f"[config] Worker model: {cheap}")
    else:
        print("[config] No API providers detected. Set AZURE_OPENAI_API_KEY, OPENAI_API_KEY, or OPENROUTER_API_KEY.")

    orchestrator = Orchestrator(config=config)

    orchestrator.register_agents(*create_specialist_agents(mesh=True))

    return orchestrator


def print_agent_catalog():
    print("Built-in agents:")
    for pillar, names in summarize_catalog().items():
        print(f"\n{pillar.upper()} pillar:")
        for name in names:
            spec = next(s for s in AGENT_SPECS if s.name == name)
            print(f"  {spec.name:<18} - {spec.description}")
    print("\nCustom agents can be loaded via --custom-agents")


def print_council_decision(decision):
    print("\nCOUNCIL MEETING")
    print(f"Question: {decision.question}")
    print(f"Vote: {decision.vote_line}")
    print(f"Verdict: {decision.verdict}")
    print(f"Confidence: {decision.confidence}%")
    if decision.conflicts:
        print(f"Conflicts: {', '.join(decision.conflicts)}")
    print("\nReasoning:")
    for opinion in decision.opinions:
        print(f"  - {opinion.agent_name}: {opinion.stance} ({opinion.confidence}%)")
        print(f"    {opinion.reasoning}")
        if opinion.evidence:
            print(f"    Evidence: {'; '.join(opinion.evidence)}")
        if opinion.risks:
            print(f"    Risks: {'; '.join(opinion.risks)}")


async def run_headless(orchestrator: Orchestrator, prompt: str):
    print(f"\n{'='*60}")
    print(f" SWARM RUN")
    print(f"{'='*60}")
    print(f" Input: {prompt}")
    print(f"{'='*60}\n")

    state = await orchestrator.run(prompt, verbose=True)

    print(f"\n{'='*60}")
    print(f" RESULT")
    print(f"{'='*60}")

    if state.agent_turns:
        final = state.agent_turns[-1]
        print(f"\nFinal agent: {final.agent_name}")
        print(f"Output: {final.output[:2000]}")
        if len(final.output) > 2000:
            print("... (truncated)")

    if state.artifacts:
        print(f"\nArtifacts created:")
        for key in state.artifacts:
            print(f"  - {key}")

    ab_test = state.get_artifact("ab_test")
    if ab_test:
        print("\nA/B Council Selection:")
        print(f"  Winner: version {ab_test['winner_id']}")
        for candidate in ab_test["candidates"]:
            marker = "SELECTED" if candidate["id"] == ab_test["winner_id"] else "ALTERNATIVE"
            print(f"  {marker} {candidate['id']}: {candidate['name']} (score {candidate['score']})")
            print(f"    {candidate['strategy']}")

    print(f"\nStats: {state.iteration} turns | {state.metadata.get('total_tokens', 0)} tokens | "
          f"{state.metadata.get('total_duration_ms', 0)}ms")

    save_dir = Path("swarm_state")
    save_dir.mkdir(exist_ok=True)
    state.save(str(save_dir / f"run_{len(list(save_dir.iterdir()))}.json"))
    print(f"\nSession saved to swarm_state/")


async def run_interactive(orchestrator: Orchestrator):
    print(f"\n{'='*60}")
    print(f" AGENT SWARM — Interactive Mode")
    print(f"{'='*60}")
    print(f" Agents: {list(orchestrator.agents.keys())}")
    print(f" Type 'exit' to quit, 'agents' to list agents")
    print(f"{'='*60}\n")

    state = SharedState()

    while True:
        try:
            prompt = input(">>> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not prompt:
            continue
        if prompt.lower() in ("exit", "quit"):
            break
        if prompt.lower() == "agents":
            print("Registered agents:")
            for name, agent in orchestrator.agents.items():
                print(f"  - {name}: {agent.description}")
            continue
        if prompt.lower() == "help":
            print("Commands:")
            print("  exit/quit    - Exit")
            print("  agents       - List agents")
            print("  help         - This help")
            print("  Any text     - Run the swarm")
            continue

        state = await orchestrator.run(prompt, verbose=True, state=state)

        if state.agent_turns:
            final = state.agent_turns[-1]
            print(f"\n[Result from {final.agent_name}]")
            print(final.output[:1500])
            if len(final.output) > 1500:
                print("... (truncated)")

    state.save("swarm_state/last_session.json")
    print("Session saved.")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Agent Swarm — Multi-Agent Orchestration")
    parser.add_argument("prompt", nargs="?", help="Run in headless mode with this prompt")
    parser.add_argument("--headless", action="store_true", help="Force headless mode")
    parser.add_argument("--config", help="Path to config file")
    parser.add_argument("--list-agents", action="store_true", help="List available agents and exit")
    parser.add_argument("--custom-agents", help="Path to JSON file with custom agent definitions")
    parser.add_argument("--council", action="store_true", help="Run an agent council vote for the prompt")
    parser.add_argument("--dashboard", nargs="?", const="examples/agent_swarm_dashboard.html", help="Export a real-time dashboard HTML file")

    args = parser.parse_args()

    if args.list_agents:
        print_agent_catalog()
        return

    orchestrator = build_default_swarm()

    if args.custom_agents:
        custom = load_custom_agents(args.custom_agents)
        for agent in custom:
            orchestrator.register_agent(agent)
            print(f"[config] Loaded custom agent: {agent.name}")

    council_decision = None
    if args.council:
        prompt = args.prompt or input("Council question: ")
        council_decision = run_council_vote(prompt, list(orchestrator.agents.values()))
        print_council_decision(council_decision)
        if not args.dashboard and not args.headless:
            return

    if args.dashboard:
        prompt = args.prompt or "should we add dark mode?"
        if council_decision is None:
            council_decision = run_council_vote(prompt, list(orchestrator.agents.values()))
        provider_assignments = assign_distinct_provider_models(
            list(orchestrator.agents.values()),
            orchestrator.config,
            include_sub_agents=True,
        )
        ab_test = run_ab_test(prompt, list(orchestrator.agents.values())[:8]).to_dict()
        dashboard_path = write_dashboard(
            args.dashboard,
            list(orchestrator.agents.values()),
            council_decision,
            provider_assignments,
            ab_test,
        )
        print(f"[dashboard] Wrote {dashboard_path}")
        if not args.headless:
            return

    if args.prompt or args.headless:
        prompt = args.prompt or input("Enter prompt: ")
        asyncio.run(run_headless(orchestrator, prompt))
    else:
        asyncio.run(run_interactive(orchestrator))


if __name__ == "__main__":
    main()
