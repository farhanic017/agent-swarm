import pytest
from swarm.core.agent import Agent
from swarm.core.handoff import build_handoff_tools, parse_handoff


def test_build_handoff_tools():
    agents = {
        "agent_a": Agent(name="agent_a", system_prompt="A"),
        "agent_b": Agent(name="agent_b", system_prompt="B", description="Helper B"),
    }

    tools = build_handoff_tools(agents, "agent_a")
    assert len(tools) >= 1

    transfer_names = [t["function"]["name"] for t in tools]
    assert "transfer_to_agent_b" in transfer_names


def test_build_handoff_tools_restricted():
    agents = {
        "agent_a": Agent(name="agent_a", system_prompt="A", handoff_targets=["agent_b"]),
        "agent_b": Agent(name="agent_b", system_prompt="B"),
        "agent_c": Agent(name="agent_c", system_prompt="C"),
    }

    tools = build_handoff_tools(agents, "agent_a")
    transfer_names = [t["function"]["name"] for t in tools]
    assert "transfer_to_agent_b" in transfer_names
    assert "transfer_to_agent_c" not in transfer_names


def test_parse_handoff():
    agents = {
        "agent_b": Agent(name="agent_b", system_prompt="B"),
    }

    tool_calls = [{
        "id": "call_1",
        "type": "function",
        "function": {
            "name": "transfer_to_agent_b",
            "arguments": '{"context": "Please analyze this data"}',
        },
    }]

    result = parse_handoff(tool_calls, agents)
    assert result is not None
    name, context = result
    assert name == "agent_b"
    assert "analyze" in context


def test_parse_handoff_no_match():
    agents = {
        "agent_b": Agent(name="agent_b", system_prompt="B"),
    }
    tool_calls = [{
        "id": "call_1",
        "type": "function",
        "function": {
            "name": "get_weather",
            "arguments": "{}",
        },
    }]
    assert parse_handoff(tool_calls, agents) is None


def test_parse_handoff_invalid_json():
    agents = {
        "agent_b": Agent(name="agent_b", system_prompt="B"),
    }
    tool_calls = [{
        "id": "call_1",
        "type": "function",
        "function": {
            "name": "transfer_to_agent_b",
            "arguments": "not valid json",
        },
    }]
    result = parse_handoff(tool_calls, agents)
    assert result is None
