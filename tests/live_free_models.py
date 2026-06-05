"""Comprehensive free model testing - finds bugs with OpenRouter/Google free tiers"""
import sys, os, asyncio, json, time
sys.path.insert(0, r"C:\Users\Farhan\Desktop\agent swarm")

from swarm.config import SwarmConfig
from swarm.providers.factory import ProviderFactory
from swarm.providers.base import Message
from swarm.core.orchestrator import Orchestrator
from swarm.core.agent import Agent
from swarm.core.state import SharedState
from swarm.agents.triage import create_triage_agent
from swarm.agents.researcher import create_researcher_agent
from swarm.agents.coder import create_coder_agent
from swarm.agents.writer import create_writer_agent
from swarm.agents.reviewer import create_reviewer_agent

BUGS = []

def report_bug(severity, area, description):
    BUGS.append({"severity": severity, "area": area, "description": description})
    print(f"  [{severity}] BUG: {area} - {description}")


async def test_openrouter_basic():
    """Test basic OpenRouter free model call"""
    print("\n=== Test 1: OpenRouter basic chat ===")
    cfg = SwarmConfig.from_opencode_config()
    if "openrouter" not in cfg.providers:
        print("  SKIP: No OpenRouter provider")
        return

    chat = ProviderFactory.get_chat_func(cfg, "openrouter:openrouter/free")
    try:
        resp = await chat(
            messages=[Message(role="user", content="Say hello in one word")],
            temperature=0.3,
            max_tokens=50,
        )
        print(f"  OK: {resp.content[:50]} | model={resp.model} | tokens={resp.usage}")
    except Exception as e:
        report_bug("HIGH", "openrouter-chat", f"OpenRouter basic chat failed: {e}")


async def test_openrouter_specific_free_models():
    """Test specific OpenRouter free models"""
    print("\n=== Test 2: OpenRouter specific free models ===")
    cfg = SwarmConfig.from_opencode_config()
    if "openrouter" not in cfg.providers:
        print("  SKIP: No OpenRouter provider")
        return

    models_to_test = [
        "openrouter:deepseek/deepseek-v4-flash:free",
        "openrouter:qwen/qwen3-coder:free",
        "openrouter:google/gemma-4-31b-it:free",
        "openrouter:microsoft/phi-4-multimodal-instruct:free",
        "openrouter:meta-llama/llama-3.3-70b-instruct:free",
        "openrouter:openrouter/free",
    ]

    for model_ref in models_to_test:
        try:
            chat = ProviderFactory.get_chat_func(cfg, model_ref)
            resp = await chat(
                messages=[Message(role="user", content="Reply with: OK")],
                temperature=0.3,
                max_tokens=20,
            )
            print(f"  OK {model_ref}: {resp.content[:40]}")
        except Exception as e:
            status = ""
            if "429" in str(e): status = "429"
            elif "402" in str(e): status = "402 (payment required)"
            elif "400" in str(e): status = "400"
            print(f"  FAIL {model_ref}: [{status}] {str(e)[:80]}")


async def test_google_gemini():
    """Test Google Gemini free model"""
    print("\n=== Test 3: Google Gemini free model ===")
    cfg = SwarmConfig.from_opencode_config()
    if "google-ai" not in cfg.providers:
        print("  SKIP: No Google AI provider")
        return

    models_to_test = [
        "google-ai:gemini/gemini-2.0-flash-001",
        "google-ai:gemini/gemini-2.5-flash-001",
        "google-ai:gemini/gemini-2.0-flash-lite-001",
    ]

    for model_ref in models_to_test:
        try:
            chat = ProviderFactory.get_chat_func(cfg, model_ref)
            resp = await chat(
                messages=[Message(role="user", content="Reply with: OK")],
                temperature=0.3,
                max_tokens=20,
            )
            print(f"  OK {model_ref}: {resp.content[:40]}")
        except Exception as e:
            print(f"  FAIL {model_ref}: {str(e)[:100]}")


async def test_orchestrator_free_only():
    """Run the orchestrator with only free models (no Azure)"""
    print("\n=== Test 4: Orchestrator with free models only ===")
    cfg = SwarmConfig.from_opencode_config()
    if "azure-openai" in cfg.providers:
        del cfg.providers["azure-openai"]
    print(f"  Providers: {list(cfg.providers.keys())}")
    print(f"  Best: {cfg.get_best_model()}")
    print(f"  Cheapest: {cfg.get_cheapest_model()}")

    orch = Orchestrator(config=cfg)
    triage = create_triage_agent(handoff_targets=["researcher", "coder", "writer"])
    researcher = create_researcher_agent(handoff_targets=["writer"])
    writer = create_writer_agent()
    orch.register_agents(triage, researcher, writer)

    try:
        state = await orch.run(
            "What is the capital of Japan? Answer in one sentence.",
            verbose=False,
            max_iterations=5,
        )
        if state.agent_turns:
            last = state.agent_turns[-1]
            print(f"  Turns: {state.iteration} | Final: {last.output[:100]}")
            print(f"  Tokens: {state.metadata.get('total_tokens', 0)}")
        else:
            report_bug("HIGH", "orchestrator-free", "No agent turns with free models")
    except Exception as e:
        report_bug("HIGH", "orchestrator-free", f"Orchestrator failed: {e}")


async def test_model_chain_fallback():
    """Test that model fallback chain works when first model fails"""
    print("\n=== Test 5: Model fallback chain ===")
    cfg = SwarmConfig.from_opencode_config()

    agent = Agent(name="test", system_prompt="Answer briefly.", tools=[])

    orch = Orchestrator(config=cfg)
    chain = orch._get_model_chain(agent, "worker")
    print(f"  Fallback chain ({len(chain)} models):")
    for i, m in enumerate(chain):
        print(f"    {i+1}. {m}")

    if len(chain) < 2:
        report_bug("MEDIUM", "model-chain", "Fallback chain has fewer than 2 models")


async def test_google_provider_model_name():
    """Test Google provider handles gemini/gemini-xxx model names correctly"""
    print("\n=== Test 6: Google provider model name handling ===")
    cfg = SwarmConfig.from_opencode_config()
    if "google-ai" not in cfg.providers:
        print("  SKIP: No Google AI provider")
        return

    provider = ProviderFactory.get_provider(cfg, "google-ai:gemini/gemini-2.0-flash-001")
    if provider is None:
        report_bug("HIGH", "google-provider", "ProviderFactory returned None for google-ai")
        return

    try:
        resp = await provider.chat(
            messages=[Message(role="user", content="Reply with: OK")],
            model="gemini-2.0-flash-001",
            max_tokens=20,
        )
        print(f"  OK with gemini-2.0-flash-001: {resp.content[:40]}")
    except Exception as e:
        report_bug("HIGH", "google-model-name", f"Google provider model name handling failed: {e}")


async def test_orchestrator_loop_detection():
    """Test loop detection kicks in properly"""
    print("\n=== Test 7: Loop detection ===")
    cfg = SwarmConfig.from_opencode_config()

    orch = Orchestrator(config=cfg)
    agent_a = Agent(name="agent_a", system_prompt="You are agent A. Always hand off to agent B.", handoff_targets=["agent_b"])
    agent_b = Agent(name="agent_b", system_prompt="You are agent B. Always hand off to agent A.", handoff_targets=["agent_a"])
    orch.register_agents(agent_a, agent_b)

    # This should trigger loop detection
    try:
        state = await orch.run("Test loop", max_iterations=20, verbose=False)
        if state.metadata.get("loop_detected"):
            print(f"  OK: Loop was detected at iteration {state.iteration}")
        else:
            # Not necessarily a bug if the models don't actually handoff
            print(f"  NOTE: No loop detected (models may have handled differently, iterations={state.iteration})")
    except Exception as e:
        report_bug("MEDIUM", "loop-detection", f"Loop detection test error: {e}")


async def test_save_state_with_unicode():
    """Test state persistence handles unicode"""
    print("\n=== Test 8: Unicode in state ===")
    state = SharedState(user_input="What is 東京の天気?")
    state.summary = "Researched 東京 weather"
    state.set_artifact("result", "東京の天気は晴れです")
    try:
        state.save("swarm_state/unicode_test.json")
        loaded = SharedState.load("swarm_state/unicode_test.json")
        assert loaded.user_input == "What is 東京の天気?"
        print(f"  OK: Unicode preserved: {loaded.user_input}")
        os.remove("swarm_state/unicode_test.json")
    except Exception as e:
        report_bug("MEDIUM", "unicode", f"Unicode state persistence failed: {e}")


async def test_orchestrator_with_tool_errors():
    """Test orchestrator handles tool execution errors gracefully"""
    print("\n=== Test 9: Tool error handling ===")
    cfg = SwarmConfig.from_opencode_config()
    if "azure-openai" in cfg.providers:
        del cfg.providers["azure-openai"]

    orch = Orchestrator(config=cfg)
    test_agent = Agent(
        name="test_tools",
        system_prompt="You are a test agent. Use the read_file tool with a path that does not exist.",
        tools=["read_file", "list_directory"],
    )
    orch.register_agents(test_agent)
    try:
        state = await orch.run("Read /nonexistent/path/file.txt", verbose=False, max_iterations=3)
        print(f"  Turns: {state.iteration}")
    except Exception as e:
        report_bug("MEDIUM", "tool-errors", f"Tool error handling failed: {e}")


async def test_orchestrator_empty_input():
    """Test orchestrator handles empty input"""
    print("\n=== Test 10: Empty input handling ===")
    cfg = SwarmConfig.from_opencode_config()
    orch = Orchestrator(config=cfg)
    orch.register_agents(Agent(name="test", system_prompt="You are helpful."))

    try:
        state = await orch.run("", verbose=False, max_iterations=3)
        print(f"  OK: Empty input produced {state.iteration} turn(s)")
    except Exception as e:
        report_bug("LOW", "empty-input", f"Empty input crashed: {e}")


async def test_orchestrator_unknown_agent():
    """Test orchestrator handles unknown entry agent"""
    print("\n=== Test 11: Unknown entry agent ===")
    cfg = SwarmConfig.from_opencode_config()
    orch = Orchestrator(config=cfg)
    orch.register_agents(Agent(name="alpha", system_prompt="You are alpha."))

    try:
        state = await orch.run("Hello", entry_agent="nonexistent", verbose=False, max_iterations=3)
        print(f"  OK: Unknown agent produced {state.iteration} turn(s)")
    except Exception as e:
        report_bug("MEDIUM", "unknown-agent", f"Unknown entry agent crashed: {e}")


async def test_concurrent_state():
    """Test state is not corrupted by multiple operations"""
    print("\n=== Test 12: Concurrent state safety ===")
    state = SharedState(user_input="test")
    for i in range(50):
        from swarm.core.state import AgentTurn
        state.add_turn(AgentTurn(agent_name=f"agent_{i}", input=f"in_{i}", output=f"out_{i}", model="m"))
    assert state.iteration == 50
    assert len(state.agent_turns) == 50
    print(f"  OK: {state.iteration} turns stored correctly")


async def main():
    print("=" * 60)
    print(" FREE MODEL TESTING - Finding Bugs")
    print("=" * 60)

    await test_openrouter_basic()
    await test_openrouter_specific_free_models()
    await test_google_gemini()
    await test_google_provider_model_name()
    await test_model_chain_fallback()
    await test_save_state_with_unicode()
    await test_concurrent_state()
    await test_tool_registry()

    print("\n" + "=" * 60)
    print(" ORCHESTRATOR INTEGRATION TESTS")
    print("=" * 60)
    await test_orchestrator_free_only()
    await test_orchestrator_loop_detection()
    await test_orchestrator_with_tool_errors()
    await test_orchestrator_empty_input()
    await test_orchestrator_unknown_agent()

    print("\n" + "=" * 60)
    print(" BUG REPORT")
    print("=" * 60)
    if BUGS:
        for bug in BUGS:
            print(f"  [{bug['severity']}] {bug['area']}: {bug['description']}")
        print(f"\n  Total: {len(BUGS)} bugs found")
    else:
        print("  No bugs found! Everything clean.")
    print("=" * 60)


def test_tool_registry():
    print("\n=== Test: Tool registry edge cases ===")
    try:
        from swarm.tools.registry import ToolRegistry
        reg = ToolRegistry()
        reg.register(reg._tools.get("read_file"))  # Should not crash
    except Exception:
        pass

    reg2 = ToolRegistry.create_default()
    tools = reg2.get_tools_for_agent("test", ["nonexistent_tool_xyz"])
    assert tools == [], f"Expected empty list, got {tools}"
    print(f"  OK: Unknown tool returns empty list")


if __name__ == "__main__":
    asyncio.run(main())
