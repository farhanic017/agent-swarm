"""Tests for TerminalTools — run_command, timeout, error handling."""

from __future__ import annotations
import pytest
import asyncio
from swarm.tools.terminal import TerminalTools, _split_command


class TestSplitCommand:
    def test_simple(self):
        assert _split_command("echo hello") == ["echo", "hello"]

    def test_quoted(self):
        assert _split_command('echo "hello world"') == ["echo", "hello world"]

    def test_single_quoted(self):
        assert _split_command("echo 'hello world'") == ["echo", "hello world"]

    def test_empty(self):
        assert _split_command("") == [""]

    def test_mixed_quotes(self):
        assert _split_command("cmd --name 'John Doe' --path /tmp") == ["cmd", "--name", "John Doe", "--path", "/tmp"]


@pytest.mark.asyncio
async def test_run_command_timeout():
    """Timeout should kill the process and return a TIMEOUT message."""
    result = await TerminalTools.run_command(
        "powershell.exe Start-Sleep -Seconds 30", timeout=1
    )
    assert "[TIMEOUT after 1s]" in result


@pytest.mark.asyncio
async def test_run_command_file_not_found():
    result = await TerminalTools.run_command("nonexistent_command_xyz", timeout=5)
    assert "[ERROR]" in result or "not found" in result


@pytest.mark.asyncio
async def test_run_command_success():
    result = await TerminalTools.run_command(
        "powershell.exe Write-Output hello", timeout=10
    )
    assert "[exit code 0]" in result
    assert "hello" in result
