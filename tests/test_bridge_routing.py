"""Tests for per-task model routing, fallback chains, auto-switch, and parallel execution."""

from __future__ import annotations
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

from swarm.core.orchestrator import Orchestrator
from swarm.core.agent import Agent, resolve_task_type, AGENT_TASK_MAP
from swarm.core.state import SharedState
from swarm.providers.base import LLMResponse


# ── Fixtures ──────────────────────────────────────────────────────────────

@pytest.fixture
def mock_config():
    """Create a config-like object with proper timeout."""
    cfg = MagicMock()
    cfg.agent_timeout_seconds = 60
    return cfg


@pytest.fixture
def mock_bridge():
    """Create a SwitcherBridge with mocked health/discovery."""
    with patch("swarm.switcher.bridge.SwitcherBridge") as mock:
        bridge = MagicMock()
        bridge.get_model_chain_for_task.return_value = [
            "openrouter:openrouter/free",
            "google-ai:gemini/gemini-2.5-flash-001",
        ]
        bridge.get_model_chain.return_value = [
            "openrouter:openrouter/free",
        ]
        bridge.is_healthy.return_value = True
        bridge.record_failure.return_value = None
        bridge.record_success.return_value = None
        bridge.switch_if_needed.return_value = None
        bridge.get_stable_chain_for_task.return_value = [
            "openrouter:openrouter/free",
        ]
        mock.return_value = bridge
        yield bridge


@pytest.fixture
def mock_chat():
    """Mock chat function returning a simple response."""
    fn = AsyncMock()
    fn.return_value = LLMResponse(
        content="Task complete.",
        model="test-model",
        provider="test",
        tool_calls=None,
        usage={"total_tokens": 50},
    )
    return fn


@pytest.fixture
def agents():
    return {
        "triage": Agent(
            name="triage",
            system_prompt="You route tasks.",
            description="Task router",
            task_type="general",
        ),
        "researcher": Agent(
            name="researcher",
            system_prompt="You research deeply.",
            description="Deep researcher",
            task_type="reasoning",
        ),
        "coder": Agent(
            name="coder",
            system_prompt="You write code.",
            description="Code writer",
            task_type="coding",
        ),
        "writer": Agent(
            name="writer",
            system_prompt="You write content.",
            description="Content writer",
            task_type="chat",
        ),
    }


# ── Task Routing Tests ────────────────────────────────────────────────────

class TestTaskTypeResolution:
    def test_resolve_from_field(self):
        agent = Agent(name="custom", system_prompt="", task_type="reasoning")
        assert resolve_task_type(agent) == "reasoning"

    def test_resolve_from_map(self):
        for name, expected in AGENT_TASK_MAP.items():
            agent = Agent(name=name, system_prompt="")
            assert resolve_task_type(agent) == expected, f"{name} -> {expected}"

    def test_resolve_default(self):
        agent = Agent(name="unknown", system_prompt="")
        assert resolve_task_type(agent) == "general"


class TestPerTaskModelRouting:
    def test_different_agents_get_different_chains(self, mock_bridge, mock_config, agents):
        """Each agent type should get a model chain optimized for its task."""
        orch = Orchestrator(config=mock_config)
        orch.switcher_bridge = mock_bridge
        for agent in agents.values():
            orch.register_agent(agent)

        chains = {}
        for name, agent in agents.items():
            chains[name] = orch._get_model_chain(agent, "worker")

        # Verify bridge was called with correct task types
        calls = mock_bridge.get_model_chain_for_task.call_args_list
        task_types = [c[0][0] for c in calls if c[0]]
        assert "general" in task_types
        assert "reasoning" in task_types
        assert "coding" in task_types
        assert "chat" in task_types

    def test_bridge_fallback_when_task_specific_empty(self, mock_bridge, mock_config, agents):
        """When get_model_chain_for_task returns empty, fall back to get_model_chain."""
        mock_bridge.get_model_chain_for_task.return_value = []

        orch = Orchestrator(config=mock_config)
        orch.switcher_bridge = mock_bridge
        for agent in agents.values():
            orch.register_agent(agent)

        chain = orch._get_model_chain(agents["coder"], "worker")
        assert len(chain) > 0
        assert mock_bridge.get_model_chain.called

    def test_parallel_uses_task_specific_chains(self, mock_bridge, mock_config, agents):
        """run_parallel should use per-task model chains for each agent."""
        orch = Orchestrator(config=mock_config)
        orch.switcher_bridge = mock_bridge
        for agent in agents.values():
            orch.register_agent(agent)

        tasks = [("coder", "write code"), ("researcher", "research"), ("writer", "write")]
        state = SharedState(user_input="complex task")

        # Mock _chat_with_fallback to avoid real API calls
        orch._chat_with_fallback = AsyncMock()
        orch._chat_with_fallback.return_value = (
            LLMResponse(content="Done", model="test", provider="test", usage={}),
            "openrouter:openrouter/free",
        )

        results = asyncio.run(orch.run_parallel(tasks, state))

        assert len(results) == 3
        for name, output, success in results:
            assert success, f"{name} should succeed"
            assert output


# ── Fallback Chain Tests ───────────────────────────────────────────────────

class TestFallbackChain:
    @pytest.mark.asyncio
    async def test_first_model_succeeds(self, mock_bridge, mock_config, mock_chat):
        """The first healthy model in the chain should be used."""
        with patch("swarm.providers.factory.ProviderFactory.get_chat_func") as get_func:
            get_func.return_value = mock_chat

            orch = Orchestrator(config=mock_config)
            orch.switcher_bridge = mock_bridge
            coder = Agent(name="coder", system_prompt="", task_type="coding")
            orch.register_agent(coder)

            response, model_ref = await orch._chat_with_fallback(
                messages=[], tools=None,
                temperature=0.3, max_tokens=1000,
                model_chain=["openrouter:openrouter/free"],
                agent_name="coder",
            )
            assert model_ref == "openrouter:openrouter/free"
            assert response.content == "Task complete."

    @pytest.mark.asyncio
    async def test_fallback_to_second_model(self, mock_bridge, mock_config):
        """When the first model fails, fall back to the next in chain."""
        fail_fn = AsyncMock()
        fail_fn.side_effect = Exception("429 rate limit")

        success_fn = AsyncMock()
        success_fn.return_value = LLMResponse(
            content="Backup worked.", model="gemini", provider="google-ai",
            usage={"total_tokens": 30},
        )

        def get_func(config, model_ref):
            return fail_fn if "free" in model_ref else success_fn

        with patch("swarm.providers.factory.ProviderFactory.get_chat_func") as get_func_mock:
            get_func_mock.side_effect = get_func

            orch = Orchestrator(config=mock_config)
            orch.switcher_bridge = mock_bridge
            orch.register_agent(Agent(name="coder", system_prompt="", task_type="coding"))

            response, model_ref = await orch._chat_with_fallback(
                messages=[], tools=None,
                temperature=0.3, max_tokens=1000,
                model_chain=[
                    "openrouter:openrouter/free",
                    "google-ai:gemini/gemini-2.5-flash-001",
                ],
                agent_name="coder",
            )
            assert model_ref == "google-ai:gemini/gemini-2.5-flash-001"
            assert "Backup" in response.content
            assert mock_bridge.record_failure.called

    @pytest.mark.asyncio
    async def test_all_models_fail(self, mock_bridge, mock_config):
        """When every model fails, raise RuntimeError."""
        fail_fn = AsyncMock()
        fail_fn.side_effect = Exception("429 rate limit")

        with patch("swarm.providers.factory.ProviderFactory.get_chat_func") as get_func:
            get_func.return_value = fail_fn

            orch = Orchestrator(config=mock_config)
            orch.switcher_bridge = mock_bridge
            orch.register_agent(Agent(name="coder", system_prompt="", task_type="coding"))

            with pytest.raises(RuntimeError, match="All models exhausted"):
                await orch._chat_with_fallback(
                    messages=[], tools=None,
                    temperature=0.3, max_tokens=1000,
                    model_chain=["openrouter:openrouter/free"],
                    agent_name="coder",
                )


# ── Auto-Switch Tests ─────────────────────────────────────────────────────

class TestAutoSwitch:
    @pytest.mark.asyncio
    async def test_auto_switch_when_all_depleted(self, mock_bridge, mock_config):
        """After all models fail, auto-switch should try a refreshed chain."""
        fail_fn = AsyncMock()
        fail_fn.side_effect = Exception("402 payment required")

        mock_bridge.switch_if_needed.return_value = "google-ai:gemini/gemini-2.5-flash-001"
        mock_bridge.get_model_chain.return_value = ["google-ai:gemini/gemini-2.5-flash-001"]

        with patch("swarm.providers.factory.ProviderFactory.get_chat_func") as get_func:
            def side_effect(config, model_ref):
                if "gemini" in model_ref:
                    success = AsyncMock()
                    success.return_value = LLMResponse(
                        content="Recovered via switch.",
                        model="gemini", provider="google-ai",
                        usage={"total_tokens": 20},
                    )
                    return success
                return fail_fn
            get_func.side_effect = side_effect

            orch = Orchestrator(config=mock_config)
            orch.switcher_bridge = mock_bridge
            orch.register_agent(Agent(name="coder", system_prompt="", task_type="coding"))

            response, model_ref = await orch._chat_with_fallback(
                messages=[], tools=None,
                temperature=0.3, max_tokens=1000,
                model_chain=["openrouter:openrouter/free"],
                agent_name="coder",
            )
            assert model_ref == "google-ai:gemini/gemini-2.5-flash-001"
            assert "Recovered via switch" in response.content

    @pytest.mark.asyncio
    async def test_cooldown_skips_depleted_models(self, mock_bridge, mock_config):
        """Depleted models should be skipped during fallback."""
        mock_bridge.is_healthy.side_effect = lambda ref: "healthy" in ref

        success_fn = AsyncMock()
        success_fn.return_value = LLMResponse(
            content="Healthy model worked.", model="healthy", provider="test",
            usage={},
        )

        with patch("swarm.providers.factory.ProviderFactory.get_chat_func") as get_func:
            get_func.return_value = success_fn

            orch = Orchestrator(config=mock_config)
            orch.switcher_bridge = mock_bridge
            orch.register_agent(Agent(name="coder", system_prompt="", task_type="coding"))

            response, model_ref = await orch._chat_with_fallback(
                messages=[], tools=None,
                temperature=0.3, max_tokens=1000,
                model_chain=[
                    "depleted:model1",
                    "depleted:model2",
                    "healthy:model",
                ],
                agent_name="coder",
            )
            assert model_ref == "healthy:model"
            # verify only the healthy model was fetched from the factory
            get_func.assert_called_once_with(mock_config, "healthy:model")


# ── Parallel Execution Tests ────────────────────────────────────────────────

class TestParallelExecution:
    @pytest.mark.asyncio
    async def test_run_parallel_all_succeed(self, mock_config, agents):
        """Multiple agents running in parallel should all complete."""
        orch = Orchestrator(config=mock_config)

        # Mock the bridge
        with patch("swarm.switcher.bridge.SwitcherBridge") as bridge_cls:
            bridge = MagicMock()
            bridge.get_model_chain_for_task.return_value = ["openrouter:openrouter/free"]
            bridge.get_model_chain.return_value = ["openrouter:openrouter/free"]
            bridge.is_healthy.return_value = True
            bridge_cls.return_value = bridge
            orch.switcher_bridge = bridge

            for agent in agents.values():
                orch.register_agent(agent)

            # Mock chat to avoid real API
            orch._chat_with_fallback = AsyncMock()
            orch._chat_with_fallback.return_value = (
                LLMResponse(content="Parallel work done.", model="test", provider="test", usage={}),
                "openrouter:openrouter/free",
            )

            tasks = [
                ("coder", "build a React component"),
                ("researcher", "find best React patterns"),
                ("writer", "document the component"),
            ]
            state = SharedState(user_input="build a React app")
            results = await orch.run_parallel(tasks, state)

            assert len(results) == 3
            for name, output, success in results:
                assert success, f"{name} failed"
                assert "Parallel work done" in output

    @pytest.mark.asyncio
    async def test_run_parallel_partial_failure(self, mock_config, agents):
        """Some agents can fail while others succeed."""
        orch = Orchestrator(config=mock_config)

        with patch("swarm.switcher.bridge.SwitcherBridge") as bridge_cls:
            bridge = MagicMock()
            bridge.get_model_chain_for_task.return_value = ["openrouter:openrouter/free"]
            bridge.get_model_chain.return_value = ["openrouter:openrouter/free"]
            bridge.is_healthy.return_value = True
            bridge_cls.return_value = bridge
            orch.switcher_bridge = bridge

            for agent in agents.values():
                orch.register_agent(agent)

            call_count = 0
            async def failing_chat(messages, tools, temperature, max_tokens, model_chain, agent_name):
                nonlocal call_count
                call_count += 1
                if call_count == 2:  # second call fails
                    raise RuntimeError("All models exhausted for researcher")
                return (
                    LLMResponse(content="Done.", model="test", provider="test", usage={}),
                    "openrouter:openrouter/free",
                )
            orch._chat_with_fallback = failing_chat

            tasks = [
                ("coder", "write code"),
                ("researcher", "deep research"),
                ("writer", "write docs"),
            ]
            state = SharedState(user_input="project")
            results = await orch.run_parallel(tasks, state)

            assert len(results) == 3
            # coder and writer succeed, researcher fails
            by_name = {r[0]: r for r in results}
            assert by_name["coder"][2] is True
            assert by_name["researcher"][2] is False
            assert by_name["writer"][2] is True

    @pytest.mark.asyncio
    async def test_parallel_faster_than_serial(self, mock_config, agents):
        """Parallel execution should be faster than running agents one by one."""
        with patch("swarm.skills.loader.SkillLoader.discover") as mock_discover:
            mock_discover.return_value = None
            orch = Orchestrator(config=mock_config)

            with patch("swarm.switcher.bridge.SwitcherBridge") as bridge_cls:
                bridge = MagicMock()
                bridge.get_model_chain_for_task.return_value = ["openrouter:openrouter/free"]
                bridge.get_model_chain.return_value = ["openrouter:openrouter/free"]
                bridge.is_healthy.return_value = True
                bridge_cls.return_value = bridge
                orch.switcher_bridge = bridge

                for agent in agents.values():
                    orch.register_agent(agent)

                import time
                async def slow_chat(*args, **kwargs):
                    await asyncio.sleep(0.1)
                    return (
                        LLMResponse(content="Slow but done.", model="test", provider="test", usage={}),
                        "openrouter:openrouter/free",
                    )
                orch._chat_with_fallback = slow_chat

                tasks = [
                    ("coder", "task1"),
                    ("researcher", "task2"),
                    ("writer", "task3"),
                ]

                start = time.monotonic()
                state = SharedState(user_input="test")
                results = await orch.run_parallel(tasks, state)
                elapsed = time.monotonic() - start

                # 3 parallel tasks of 0.1s each should take < 0.2s total
                assert elapsed < 0.2, f"Parallel took {elapsed:.3f}s, expected < 0.2s"
                assert all(r[2] for r in results)


# ── Integration: Full Orchestrator with Bridge ─────────────────────────────

class TestFullStack:
    def test_agent_task_type_mapped_correctly(self):
        """Pre-built agents should have their task types auto-mapped."""
        for name in AGENT_TASK_MAP:
            agent = Agent(name=name, system_prompt=f"You are {name}")
            expected = AGENT_TASK_MAP[name]
            assert resolve_task_type(agent) == expected

    @pytest.mark.asyncio
    async def test_run_with_all_agents_parallel_execution(self, mock_config, agents):
        """End-to-end: run complex task using parallel agents."""
        orch = Orchestrator(config=mock_config)

        with patch("swarm.switcher.bridge.SwitcherBridge") as bridge_cls:
            bridge = MagicMock()
            bridge.get_model_chain_for_task.return_value = ["openrouter:openrouter/free"]
            bridge.get_model_chain.return_value = ["openrouter:openrouter/free"]
            bridge.is_healthy.return_value = True
            bridge.get_working_models.return_value = [
                ("openrouter:openrouter/free", 150, "healthy"),
            ]
            bridge.get_working_models_for_task.return_value = [
                ("openrouter:openrouter/free", 150, "healthy"),
            ]
            bridge.record_failure.return_value = None
            bridge.switch_if_needed.return_value = None
            bridge_cls.return_value = bridge
            orch.switcher_bridge = bridge

            for agent in agents.values():
                orch.register_agent(agent)

            orch._chat_with_fallback = AsyncMock()
            orch._chat_with_fallback.return_value = (
                LLMResponse(content="Complex task done.", model="test", provider="test", usage={"total_tokens": 100}),
                "openrouter:openrouter/free",
            )

            tasks = [
                ("coder", "build UI"),
                ("researcher", "find best practices"),
            ]
            state = SharedState(user_input="complex task")
            results = await orch.run_parallel(tasks, state)

            assert len(results) == 2
            assert all(r[2] for r in results)
