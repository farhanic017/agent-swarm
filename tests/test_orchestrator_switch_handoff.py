import pytest

from swarm.config import SwarmConfig
from swarm.core.orchestrator import Orchestrator
from swarm.providers.base import Message


@pytest.mark.asyncio
async def test_orchestrator_switch_context_full_once_then_remembered():
    orch = Orchestrator(config=SwarmConfig())
    await orch.consciousness.push_progress("coder", "implemented parser")
    messages = [Message(role="user", content="build the parser feature")]

    first = await orch._inject_switch_context(
        list(messages),
        "provider:model-b",
        "coder",
        ("provider:model-a", "429", "out of credits"),
    )
    second = await orch._inject_switch_context(
        list(messages),
        "provider:model-b",
        "coder",
        ("provider:model-a", "429", "out of credits"),
    )

    assert "FULL_CONTEXT_ONCE" in first[0].content
    assert "implemented parser" in first[0].content
    assert "REMEMBERED" in second[0].content
    assert "implemented parser" not in second[0].content
