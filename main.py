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
import threading
from pathlib import Path

_streaming_enabled = False

def emit_event(event_type: str, data: dict):
    """Emit a JSON event to stdout for real-time streaming to OpenCode."""
    if not _streaming_enabled:
        return
    event = {"type": event_type, **data}
    try:
        sys.stdout.write(json.dumps(event) + "\n")
        sys.stdout.flush()
    except Exception:
        pass

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

    # System awareness: read resource limits from OctoCode
    max_agents = int(os.environ.get("OCTOCODE_MAX_AGENTS", "40"))
    system_level = os.environ.get("OCTOCODE_SYSTEM_LEVEL", "safe")
    ram_gb = int(os.environ.get("OCTOCODE_RAM_GB", "8"))
    cpu_cores = int(os.environ.get("OCTOCODE_CPU_CORES", "4"))

    print(f"[config] Detected providers: {list(config.providers.keys())}")
    if config.providers:
        best = config.get_best_model()
        cheap = config.get_cheapest_model()
        print(f"[config] Best model: {best}")
        print(f"[config] Worker model: {cheap}")
    else:
        print("[config] No API providers detected. Set AZURE_OPENAI_API_KEY, OPENAI_API_KEY, or OPENROUTER_API_KEY.")

    print(f"[system] Resource level: {system_level} | RAM: {ram_gb}GB | CPU: {cpu_cores} cores | Max agents: {max_agents}")

    orchestrator = Orchestrator(config=config)

    all_agents = create_specialist_agents(mesh=True)

    # Use all agents up to system limit - swarm needs full agent mesh for council/voting
    selected = all_agents[:max_agents]

    print(f"[system] Selected {len(selected)}/{len(all_agents)} agents")

    orchestrator.register_agents(*selected)

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
    global _streaming_enabled
    _streaming_enabled = True

    emit_event("swarm_start", {"prompt": prompt})
    emit_event("status", {"message": "Initializing agents..."})

    # Hook into consciousness to stream events
    original_publish = orchestrator.consciousness.publish
    async def streaming_publish(event):
        await original_publish(event)
        if event.type == "progress":
            detail = event.payload.get("detail", {})
            emit_event("agent_progress", {
                "agent": event.source,
                "message": event.payload.get("message", ""),
                "detail": detail,
            })
        elif event.type == "state_change":
            emit_event("state_change", {
                "key": event.payload.get("key", ""),
                "source": event.source,
            })
    orchestrator.consciousness.publish = streaming_publish

    emit_event("status", {"message": "Running orchestrator..."})
    state = await orchestrator.run(prompt, verbose=True)

    emit_event("swarm_complete", {
        "turns": state.iteration,
        "tokens": state.metadata.get("total_tokens", 0),
        "duration_ms": state.metadata.get("total_duration_ms", 0),
        "agents_used": list(set(t.agent_name for t in state.agent_turns)) if state.agent_turns else [],
    })

    # Section 1: The rest (artifacts, stats, metadata)
    if state.artifacts:
        emit_event("artifacts", {"keys": list(state.artifacts.keys())})

    ab_test = state.get_artifact("ab_test")
    if ab_test:
        print(f"\n{'='*60}")
        print(f" A/B COUNCIL SELECTION")
        print(f"{'='*60}")
        print(f"  Winner: version {ab_test['winner_id']}")
        for candidate in ab_test["candidates"]:
            marker = "SELECTED" if candidate["id"] == ab_test["winner_id"] else "ALTERNATIVE"
            print(f"  {marker} {candidate['id']}: {candidate['name']} (score {candidate['score']})")
            print(f"    {candidate['strategy']}")

    save_dir = Path("swarm_state")
    save_dir.mkdir(exist_ok=True)
    state.save(str(save_dir / f"run_{len(list(save_dir.iterdir()))}.json"))

    print(f"\n{'='*60}")
    print(f" STATS")
    print(f"{'='*60}")
    print(f"  Turns: {state.iteration}")
    print(f"  Tokens: {state.metadata.get('total_tokens', 0)}")
    print(f"  Duration: {state.metadata.get('total_duration_ms', 0)}ms")
    print(f"  Session saved to swarm_state/")

    # Section 2: Council votes (if any)
    council_decision = state.get_artifact("council_decision")
    if council_decision:
        emit_event("council_decision", {
            "question": council_decision.get("question", prompt),
            "verdict": council_decision.get("verdict", "N/A"),
            "confidence": council_decision.get("confidence", 0),
            "yes_votes": council_decision.get("yes_votes", 0),
            "no_votes": council_decision.get("no_votes", 0),
            "opinions": council_decision.get("opinions", []),
        })

    # Section 3: Agent reply (at the very bottom)
    if state.agent_turns:
        final = state.agent_turns[-1]
        emit_event("agent_reply", {
            "agent": final.agent_name,
            "output": final.output[:2000],
        })


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
    parser.add_argument("--watch", action="store_true", help="Start watchdog health monitor (background model rotation)")
    parser.add_argument("--watchdog-status", action="store_true", help="Show watchdog and model health status")
    parser.add_argument("--watchdog-interval", type=int, default=120, help="Watchdog check interval in seconds (default: 120)")
    parser.add_argument("--test-failover", action="store_true", help="Test automatic model failover by simulating token exhaustion")
    parser.add_argument("--switch-history", action="store_true", help="Show model switch history for this session")
    parser.add_argument("--warmup", action="store_true", help="Pre-check all models and warm up the model chain")
    parser.add_argument("--hide-model", metavar="MODEL", help="Hide a model from the chain (format: provider:model)")
    parser.add_argument("--unhide-model", metavar="MODEL", help="Unhide a previously hidden model")
    parser.add_argument("--hidden-models", action="store_true", help="List all hidden models")
    parser.add_argument("--favorite", metavar="MODEL", help="Favorite a model (format: provider:model)")
    parser.add_argument("--unfavorite", metavar="MODEL", help="Unfavorite a model")
    parser.add_argument("--favorites", action="store_true", help="List all favorited models")
    parser.add_argument("--recent", action="store_true", help="List recently used models")
    parser.add_argument("--model-selector", nargs="?", const="examples/model_selector.html", help="Generate interactive model selector HTML")

    args = parser.parse_args()

    if args.list_agents:
        print_agent_catalog()
        return

    orchestrator = build_default_swarm()

    # Watchdog status — check model health without running a task
    if args.watchdog_status:
        import json as _json
        from swarm.switcher.switcher import (
            discover_providers, build_chain, check_all_parallel, load_state,
            get_active, detect_task, score_model, get_model_specialty,
            is_depleted, get_recovery_eta, _load_health_cache, _save_health_cache,
        )
        print("\n  Agent Swarm — Watchdog Status\n")
        providers = discover_providers()
        chain = build_chain(providers)
        print(f"  Models discovered: {len(providers)}")
        print(f"  Providers: {len(set(p['provider'] for p in providers))}")

        active_key = get_active("opencode")
        task = detect_task()
        print(f"  Active model: {active_key or '(not set)'}")
        print(f"  Detected task: {task}\n")

        state = load_state()
        depleted = state.get("depleted", {})
        if depleted:
            print(f"  Depleted models ({len(depleted)}):")
            for key, info in depleted.items():
                until = info.get("cooldown_until", "?")[:19]
                reason = info.get("reason", "unknown")[:50]
                print(f"    X {key:<45} until {until}  ({reason})")
            print()

        eta = get_recovery_eta()
        if eta.get("fastest_recovery"):
            f = eta["fastest_recovery"]
            secs = f.get("seconds_remaining", f["minutes"] * 60)
            print(f"  Fastest recovery: ~{secs}s ({f['key']})\n")

        print(f"  Health check (parallel):")
        cached = _load_health_cache()
        health = check_all_parallel(chain, cached_health=cached)
        _save_health_cache(health)

        healthy_count = 0
        for p in chain:
            key = p["key"]
            h = health.get(key, (False, "no check"))
            healthy, msg = h
            if healthy:
                healthy_count += 1
            icon = "+" if healthy else "X"
            dep = " [depleted]" if is_depleted(key) else ""
            spec, _ = get_model_specialty(p["model_id"])
            print(f"    {icon} {spec:10s} {key:<45}{dep}  {msg[:40]}")
        print(f"\n  {healthy_count}/{len(chain)} models healthy")
        return

    # Watch mode — background health monitoring with auto-rotation
    if args.watch:
        import signal
        print(f"\n  Starting watchdog (interval={args.watchdog_interval}s). Ctrl+C to stop.\n")

        async def _run_watch():
            from swarm.switcher.watchdog import Watchdog
            watchdog = Watchdog(
                bridge=orchestrator.switcher_bridge,
                consciousness=orchestrator.consciousness,
                interval=args.watchdog_interval,
            )
            await watchdog.start()
            print("  Watchdog running. Press Ctrl+C to stop.\n")
            try:
                while watchdog.is_running:
                    await asyncio.sleep(1)
            except (KeyboardInterrupt, asyncio.CancelledError):
                pass
            finally:
                status = watchdog.get_status()
                await watchdog.stop()
                print(f"\n  Watchdog stopped. Stats: {status['checks']} checks, "
                      f"{status['rotations']} rotations, {status['recoveries']} recoveries")

        try:
            asyncio.run(_run_watch())
        except KeyboardInterrupt:
            print("\n  Watchdog stopped.")
        return

    # Hidden models management
    if args.hide_model:
        from swarm.switcher.switcher import hide_model as _hide_model, discover_providers
        model = args.hide_model
        # Validate the model exists
        providers = discover_providers()
        known_keys = {p["key"] for p in providers}
        if model not in known_keys:
            print(f"\n  WARNING: '{model}' not found in discovered models.")
            print(f"  Known models: {', '.join(sorted(known_keys)[:10])}...")
            print(f"  Hiding anyway (it may appear after config changes).\n")
        _hide_model(model, reason="user CLI --hide-model")
        print(f"\n  Hidden: {model}")
        print(f"  This model will not appear in chains, health checks, or auto-rotation.\n")
        return

    if args.unhide_model:
        from swarm.switcher.switcher import unhide_model as _unhide_model
        model = args.unhide_model
        if _unhide_model(model):
            print(f"\n  Unhidden: {model}")
            print(f"  This model will now appear in chains again.\n")
        else:
            print(f"\n  '{model}' was not hidden.\n")
        return

    if args.hidden_models:
        from swarm.switcher.switcher import get_hidden_models
        hidden = get_hidden_models()
        print(f"\n  Hidden Models ({len(hidden)})\n")
        if not hidden:
            print("  No models are hidden.")
            print("  Use --hide-model provider:model to hide a model.\n")
        else:
            for i, m in enumerate(hidden, 1):
                print(f"  {i}. {m}")
            print(f"\n  Use --unhide-model provider:model to restore.\n")
        return

    # Favorites management
    if args.favorite:
        from swarm.switcher.switcher import set_favorite as _set_favorite, discover_providers
        model = args.favorite
        providers = discover_providers()
        known_keys = {p["key"] for p in providers}
        if model not in known_keys:
            print(f"\n  WARNING: '{model}' not found in discovered models.")
            print(f"  Known models: {', '.join(sorted(known_keys)[:10])}...")
            print(f"  Favoriting anyway.\n")
        _set_favorite(model)
        print(f"\n  Starred: {model}")
        print(f"  This model will appear in the Favorites category.\n")
        return

    if args.unfavorite:
        from swarm.switcher.switcher import unset_favorite as _unset_favorite
        model = args.unfavorite
        _unset_favorite(model)
        print(f"\n  Unstarred: {model}\n")
        return

    if args.favorites:
        from swarm.switcher.switcher import get_favorites
        favs = get_favorites()
        print(f"\n  Favorited Models ({len(favs)})\n")
        if not favs:
            print("  No models favorited yet.")
            print("  Use --favorite provider:model to star a model.\n")
        else:
            for i, m in enumerate(favs, 1):
                print(f"  * {m}")
            print(f"\n  Use --unfavorite provider:model to remove.\n")
        return

    if args.recent:
        from swarm.switcher.switcher import get_recent
        recent = get_recent()
        print(f"\n  Recently Used Models ({len(recent)})\n")
        if not recent:
            print("  No models used yet in this session.")
            print("  Models are tracked automatically when used.\n")
        else:
            for i, m in enumerate(recent, 1):
                print(f"  {i}. {m}")
            print()
        return

    # Interactive model selector HTML
    if args.model_selector:
        from swarm.switcher.switcher import (
            discover_providers, get_favorites, get_recent, get_hidden_models,
            get_active, detect_task, check_all_parallel, _load_health_cache,
            _save_health_cache, is_depleted, score_model, get_model_specialty,
            build_chain,
        )
        import time as _time

        print(f"\n  Generating model selector...\n")
        providers = discover_providers()
        chain = build_chain(providers)
        cached = _load_health_cache()
        health = check_all_parallel(chain, cached_health=cached)
        _save_health_cache(health)

        favs = get_favorites()
        recent = get_recent()
        hidden = get_hidden_models()
        active = get_active("opencode")
        task = detect_task()

        models_data = []
        for p in chain:
            key = p["key"]
            h = health.get(key, (False, "no check"))
            spec, _ = get_model_specialty(p["model_id"])
            models_data.append({
                "key": key,
                "provider": p["provider"],
                "model_id": p["model_id"],
                "is_free": p.get("is_free", False),
                "is_active": key == active,
                "is_fav": key in favs,
                "is_hidden": key in hidden,
                "is_depleted": is_depleted(key),
                "healthy": h[0],
                "health_msg": h[1][:60],
                "specialty": spec,
                "score": score_model(p, h, task),
            })

        models_data.sort(key=lambda x: (-x["score"]))

        payload = {
            "models": models_data,
            "favorites": favs,
            "recent": recent,
            "hidden": hidden,
            "active": active,
            "task": task,
            "total": len(models_data),
            "healthy": sum(1 for m in models_data if m["healthy"]),
        }

        output_path = args.model_selector
        from swarm.core.model_selector_html import render_model_selector
        render_model_selector(output_path, payload)
        print(f"  Model selector written to: {output_path}")
        print(f"  Open in browser to browse, star, and hide models.\n")
        return

    # Switch history — show model switches from this session
    if args.switch_history:
        from swarm.switcher.switcher import get_recovery_eta
        history = orchestrator.switcher_bridge.get_switch_history()
        print(f"\n  Model Switch History ({len(history)} switches)\n")
        if not history:
            print("  No switches recorded in this session.")
            print("  Switches are recorded when models fail and auto-rotate.\n")
        else:
            for i, entry in enumerate(history, 1):
                print(f"  {i}. {entry['from']} -> {entry['to']}")
                print(f"     Reason: {entry['reason'][:80]}")
                print(f"     Forced: {entry['forced']}  Time: {entry['time'][:19]}")
            print()
        return

    # Test failover — simulate token exhaustion and verify automatic switching
    if args.test_failover:
        print(f"\n  Testing Automatic Model Failover\n")
        bridge = orchestrator.switcher_bridge
        bridge.re_discover()
        chain = bridge.get_model_chain("best")
        if not chain:
            print("  ERROR: No models discovered. Check your config.")
            return

        print(f"  Models available: {len(chain)}")
        print(f"  Current best: {chain[0]}\n")

        # Simulate exhaustion on the first model
        test_model = chain[0]
        print(f"  Simulating token exhaustion on: {test_model}")
        from swarm.switcher.switcher import mark_depleted, is_depleted
        mark_depleted(test_model, "test-failover: simulated exhaustion", cooldown_minutes=1)
        assert is_depleted(test_model), "Model should be marked depleted"

        # Try to get the next model
        new_chain = bridge.get_model_chain("best")
        if new_chain and new_chain[0] != test_model:
            print(f"  [PASS] Failover successful: {test_model} -> {new_chain[0]}")
            print(f"  Chain has {len(new_chain)} fallback models")
        elif len(new_chain) > 1:
            print(f"  [PASS] Failover to alternate: {new_chain[0]}")
        else:
            print(f"  [WARN] No alternative models available. Only 1 model in chain.")

        # Test watchdog rotation
        from swarm.switcher.watchdog import Watchdog, is_token_exhaustion
        w = Watchdog(bridge=bridge, interval=60)
        new_model = asyncio.run(w.report_token_exhaustion(
            test_model, "402 Payment Required: 0 credits remaining"
        ))
        if new_model:
            print(f"  [PASS] Watchdog rotation: {test_model} -> {new_model}")
        else:
            print(f"  [WARN] Watchdog could not find alternative (all may be depleted)")

        # Clean up test state
        from swarm.switcher.switcher import mark_recovered
        mark_recovered(test_model)
        if new_model:
            mark_recovered(new_model)
        print(f"  Test state cleaned up.\n")
        return

    # Warmup — pre-check all models and show the healthy chain
    if args.warmup:
        import time as _time
        print(f"\n  Warming up model chain...\n")
        bridge = orchestrator.switcher_bridge
        start = _time.monotonic()
        bridge.re_discover()
        chain = bridge.get_model_chain("best")
        elapsed = _time.monotonic() - start

        print(f"  Discovered {len(chain)} models ({elapsed:.1f}s)")
        if chain:
            print(f"  Best model: {chain[0]}")
            print(f"  Fallback chain: {' -> '.join(chain[:5])}")
            if len(chain) > 5:
                print(f"  ... and {len(chain) - 5} more")
        else:
            print("  WARNING: No healthy models found!")

        stats = bridge.get_stats()
        print(f"\n  Stats: {stats['working']} working, {stats['depleted']} depleted, "
              f"{stats['total']} total")
        print(f"  Task type: {stats['task']}")
        print(f"  Active model: {stats['active'] or '(auto)'}")
        print()
        return

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
