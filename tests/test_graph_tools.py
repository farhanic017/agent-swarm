"""Tests for knowledge graph querying tools."""

from __future__ import annotations
import json
import pytest
from unittest.mock import patch, MagicMock
from swarm.tools.graph import (
    graph_search,
    graph_neighbors,
    graph_path,
    graph_explain,
    graph_stats,
    _find_nodes,
    _build_node_label,
)

SAMPLE_GRAPH = {
    "project": {
        "name": "TestProject",
        "description": "A test project",
        "languages": ["python"],
        "frameworks": ["fastapi"],
        "analyzedAt": "2026-01-01T00:00:00Z",
    },
    "nodes": [
        {"id": "file:src/main.py", "name": "main.py", "type": "file",
         "summary": "Entry point", "tags": ["entry", "main"], "filePath": "src/main.py",
         "complexity": "moderate"},
        {"id": "file:src/utils.py", "name": "utils.py", "type": "file",
         "summary": "Utility functions", "tags": ["util"], "filePath": "src/utils.py"},
        {"id": "function:src/main.py:run", "name": "run", "type": "function",
         "summary": "Main runner", "tags": ["core"], "filePath": "src/main.py",
         "source_location": "src/main.py:10"},
        {"id": "class:src/utils.py:Helper", "name": "Helper", "type": "class",
         "summary": "Helper class", "tags": ["util"], "filePath": "src/utils.py"},
        {"id": "document:README.md", "name": "README.md", "type": "document",
         "summary": "Project documentation", "tags": ["docs"], "filePath": "README.md"},
        {"id": "config:pyproject.toml", "name": "pyproject.toml", "type": "config",
         "summary": "Project config", "tags": ["config"], "filePath": "pyproject.toml"},
    ],
    "edges": [
        {"source": "file:src/main.py", "target": "file:src/utils.py", "type": "imports", "weight": 0.7},
        {"source": "file:src/main.py", "target": "function:src/main.py:run", "type": "contains", "weight": 1.0},
        {"source": "function:src/main.py:run", "target": "class:src/utils.py:Helper", "type": "calls", "weight": 0.8},
        {"source": "document:README.md", "target": "file:src/main.py", "type": "documents", "weight": 0.5},
    ],
    "layers": [
        {"id": "layer:application", "name": "Application", "description": "App layer",
         "nodeIds": ["file:src/main.py", "file:src/utils.py"]},
    ],
    "tour": [
        {"order": 1, "title": "Start Here", "description": "Entry point",
         "nodeIds": ["file:src/main.py"]},
    ],
}


@pytest.fixture
def mock_graph():
    with patch("swarm.tools.graph._load_graph") as mock:
        mock.return_value = SAMPLE_GRAPH
        yield


class TestGraphSearch:
    def test_search_finds_matches(self, mock_graph):
        result = graph_search("main")
        assert "main.py" in result
        assert "Entry point" in result

    def test_search_no_matches(self, mock_graph):
        result = graph_search("nonexistent")
        assert "No nodes matching" in result

    def test_search_empty_graph(self):
        with patch("swarm.tools.graph._load_graph", return_value={"nodes": []}):
            result = graph_search("test")
            assert "No knowledge graph found" in result

    def test_search_multiple_results(self, mock_graph):
        result = graph_search("util")
        assert "Found" in result


class TestGraphNeighbors:
    def test_neighbors_outgoing(self, mock_graph):
        result = graph_neighbors("file:src/main.py")
        assert "Outgoing" in result
        assert "utils.py" in result
        assert "imports" in result

    def test_neighbors_incoming(self, mock_graph):
        result = graph_neighbors("file:src/utils.py")
        assert "Incoming" in result
        assert "main.py" in result

    def test_neighbors_nonexistent(self, mock_graph):
        result = graph_neighbors("nonexistent")
        assert "not found" in result

    def test_neighbors_no_graph(self):
        with patch("swarm.tools.graph._load_graph", return_value={"nodes": []}):
            result = graph_neighbors("x")
            assert "No knowledge graph found" in result


class TestGraphPath:
    def test_path_found(self, mock_graph):
        result = graph_path("main", "Helper")
        assert "Path (" in result
        assert "Helper" in result

    def test_path_same_node(self, mock_graph):
        result = graph_path("main.py", "Entry point")
        assert "Path (" in result or "No nodes matching" not in result

    def test_path_no_match_source(self, mock_graph):
        result = graph_path("zzz_nonexistent", "Helper")
        assert "No nodes matching" in result

    def test_path_no_match_target(self, mock_graph):
        result = graph_path("main", "zzz_nonexistent")
        assert "No nodes matching" in result


class TestGraphExplain:
    def test_explain_node(self, mock_graph):
        result = graph_explain("file:src/main.py")
        assert "main.py" in result
        assert "Entry point" in result
        assert "Type: file" in result
        assert "imports" in result

    def test_explain_nonexistent(self, mock_graph):
        result = graph_explain("nonexistent")
        assert "not found" in result

    def test_explain_layer_membership(self, mock_graph):
        result = graph_explain("file:src/main.py")
        assert "Application" in result

    def test_explain_tour_reference(self, mock_graph):
        result = graph_explain("file:src/main.py")
        assert "Start Here" in result


class TestGraphStats:
    def test_stats_basic(self, mock_graph):
        result = graph_stats()
        assert "TestProject" in result
        assert "6" in result  # 6 nodes
        assert "4" in result  # 4 edges

    def test_stats_empty(self):
        with patch("swarm.tools.graph._load_graph", return_value={"nodes": []}):
            result = graph_stats()
            assert "No knowledge graph found" in result

    def test_stats_most_connected(self, mock_graph):
        result = graph_stats()
        assert "connections" in result


class TestInternalFunctions:
    def test_find_nodes_no_query(self, mock_graph):
        result = _find_nodes(SAMPLE_GRAPH, "main")
        assert len(result) >= 1

    def test_build_node_label(self):
        label = _build_node_label(SAMPLE_GRAPH, "file:src/main.py")
        assert "main.py" in label

    def test_build_node_label_missing(self):
        label = _build_node_label(SAMPLE_GRAPH, "nonexistent")
        assert label == "nonexistent"


class TestEdgeCases:
    def test_graph_file_missing(self):
        """graph_search should handle missing graph file (empty graph returned)."""
        with patch("swarm.tools.graph._load_graph", return_value={"nodes": [], "edges": [], "project": {}, "layers": [], "tour": []}):
            result = graph_search("test")
            assert "knowledge graph" in result.lower()

    def test_graph_empty_no_nodes_key(self):
        """graph_search should handle graph dict with no 'nodes' key."""
        with patch("swarm.tools.graph._load_graph", return_value={"project": {}}):
            result = graph_search("test")
            assert "knowledge graph" in result.lower()

    def test_path_no_graph(self):
        """graph_path should handle missing graph."""
        with patch("swarm.tools.graph._load_graph", return_value={"nodes": []}):
            result = graph_path("a", "b")
            assert "No knowledge graph found" in result

    def test_graph_search_with_spaces(self, mock_graph):
        """Search terms with spaces should behave gracefully."""
        result = graph_search("")
        assert "No nodes matching" in result or "" in result
