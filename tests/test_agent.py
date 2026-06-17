import pytest
from swarm.core.agent import Agent


def test_agent_creation():
    agent = Agent(
        name="test_agent",
        system_prompt="You are a test agent",
        tools=["search_web", "read_file"],
        handoff_targets=["other_agent"],
    )
    assert agent.name == "test_agent"
    assert "test agent" in agent.system_prompt.lower()
    assert "search_web" in agent.tools
    assert agent.can_handoff_to("other_agent")
    assert not agent.can_handoff_to("unknown")


def test_agent_no_handoff_restrictions():
    agent = Agent(
        name="unrestricted",
        system_prompt="Test",
        handoff_targets=[],
    )
    assert agent.can_handoff_to("anyone")


def test_agent_defaults():
    agent = Agent(name="defaults", system_prompt="Test")
    assert agent.temperature == 0.3
    assert agent.max_tokens == 4096
    assert agent.tools == []
    assert agent.handoff_targets == []
    assert agent.description == ""
    assert agent.model is None


def test_agent_handoff_restricted():
    agent = Agent(
        name="restricted",
        system_prompt="Test",
        handoff_targets=["a", "b"],
    )
    assert agent.can_handoff_to("a")
    assert agent.can_handoff_to("b")
    assert not agent.can_handoff_to("c")
