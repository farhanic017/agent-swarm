"""Tests for the core Tool class — execute, sync/async, error handling."""

from __future__ import annotations
import pytest
from swarm.tools.base import Tool


def test_tool_creation():
    tool = Tool(name="test", description="A test", func=lambda x: x, parameters={"type": "object"})
    assert tool.name == "test"
    assert tool.description == "A test"
    assert tool.parameters == {"type": "object"}


def test_to_openai_format():
    tool = Tool(name="test", description="A test", func=lambda x: x, parameters={"type": "object"})
    fmt = tool.to_openai_format()
    assert fmt["type"] == "function"
    assert fmt["function"]["name"] == "test"


@pytest.mark.asyncio
async def test_execute_sync_function():
    tool = Tool(name="add", description="Add two nums", func=lambda a, b: a + b, parameters={})
    result = await tool.execute(a=1, b=2)
    assert result == "3"


@pytest.mark.asyncio
async def test_execute_async_function():
    async def fetch(url: str):
        return f"data from {url}"

    tool = Tool(name="fetch", description="Fetch a URL", func=fetch, parameters={})
    result = await tool.execute(url="https://example.com")
    assert result == "data from https://example.com"


    @pytest.mark.asyncio
    async def test_execute_with_exception(self):
        def crash(x):
            raise ValueError("boom")

        tool = Tool(name="crash", description="Crashes", func=crash, parameters={})
        result = await tool.execute(x=1)
        assert result == "Error executing crash: boom"


@pytest.mark.asyncio
async def test_execute_returns_str_directly():
    tool = Tool(name="greet", description="Greet", func=lambda name: f"Hello {name}", parameters={})
    result = await tool.execute(name="World")
    assert result == "Hello World"


@pytest.mark.asyncio
async def test_execute_returns_none():
    tool = Tool(name="noop", description="Returns None", func=lambda: None, parameters={})
    result = await tool.execute()
    assert result == "None"


@pytest.mark.asyncio
async def test_execute_returns_int():
    tool = Tool(name="answer", description="Returns 42", func=lambda: 42, parameters={})
    result = await tool.execute()
    assert result == "42"


@pytest.mark.asyncio
async def test_execute_with_extra_kwargs():
    """Tool should wrap kwargs handling errors from the underlying function."""
    tool = Tool(name="no_args", description="No args", func=lambda: "done", parameters={})
    result = await tool.execute(extra="ignored")
    assert "Error executing no_args" in result
