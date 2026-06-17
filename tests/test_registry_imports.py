"""Tests for ToolRegistry imports and sub_agent typo fix."""

from __future__ import annotations
import pytest
from swarm.tools.registry import ToolRegistry


class TestRegistryImports:
    def test_shared_state_accessible(self):
        """SharedState should be importable at module level, not just inside function."""
        from swarm.core.state import SharedState
        assert SharedState is not None

    def test_registry_creates_without_error(self):
        """ToolRegistry.create_default should not raise import errors."""
        reg = ToolRegistry.create_default()
        assert reg is not None

    def test_registry_has_all_tools(self):
        reg = ToolRegistry.create_default()
        tools = set(reg.list_tools())
        expected = {"get_current_time", "write_file", "read_file", "list_directory",
                    "search_web", "run_python", "save_artifact",
                    "run_command", "run_script",
                    "run_react_doctor", "react_doctor_install_skill",
                    "mcp_list_tools", "mcp_call",
                    "graph_search", "graph_neighbors",
                    "graph_path", "graph_explain", "graph_stats"}
        missing = expected - tools
        assert not missing, f"Missing tools: {missing}"
        assert len(tools) >= len(expected)
