from __future__ import annotations

import json

import pytest

from swarm.config import SwarmConfig
from swarm.core.file_access import (
    FileAccessDenied,
    assert_allowed_path,
    describe_file_access_policy,
    secure_list_directory,
    secure_read_file,
    secure_write_file,
)
from swarm.core.graphify import build_graphify_payload, build_graphify_project_map, export_graphify_payload
from swarm.core.mcp_marketplace import list_mcp_marketplace, plan_mcp_connectors
from swarm.core.obsidian import build_obsidian_note, plan_obsidian_vault
from swarm.core.performance_benchmark import run_feature_benchmark, summarize_feature_benchmark
from swarm.tools.registry import ToolRegistry


def test_file_access_allows_configured_root(monkeypatch, tmp_path):
    monkeypatch.setenv("AGENT_SWARM_ALLOWED_ROOTS", str(tmp_path))
    target = tmp_path / "notes.md"

    assert secure_write_file(str(target), "hello") == f"Written to {target.resolve()}"
    assert secure_read_file(str(target)) == "hello"
    listed = json.loads(secure_list_directory(str(tmp_path)))
    assert str(target.resolve()) in listed


def test_file_access_blocks_path_outside_allowed_root(tmp_path):
    allowed = tmp_path / "allowed"
    blocked = tmp_path / "blocked"
    allowed.mkdir()
    blocked.mkdir()
    target = blocked / "secret.txt"
    target.write_text("nope", encoding="utf-8")

    with pytest.raises(FileAccessDenied):
        assert_allowed_path(target, "read", [allowed])


def test_file_access_blocks_sensitive_names(monkeypatch, tmp_path):
    monkeypatch.setenv("AGENT_SWARM_ALLOWED_ROOTS", str(tmp_path))
    secret = tmp_path / ".env"
    secret.write_text("API_KEY=secret", encoding="utf-8")

    with pytest.raises(FileAccessDenied):
        secure_read_file(str(secret))

    with pytest.raises(FileAccessDenied):
        secure_write_file(str(tmp_path / "private.pem"), "secret")


def test_registry_file_tools_use_security_policy(monkeypatch, tmp_path):
    monkeypatch.setenv("AGENT_SWARM_ALLOWED_ROOTS", str(tmp_path))
    registry = ToolRegistry.create_default()
    read_tool = registry.get("read_file")
    write_tool = registry.get("write_file")
    policy_tool = registry.get("describe_file_access_policy")
    target = tmp_path / "allowed.txt"

    assert write_tool is not None
    assert read_tool is not None
    assert policy_tool is not None
    write_tool.func(str(target), "safe")
    assert read_tool.func(str(target)) == "safe"
    policy = json.loads(policy_tool.func())
    assert str(tmp_path.resolve()) in policy["allowed_roots"]


def test_registry_file_tools_block_sensitive_file(monkeypatch, tmp_path):
    monkeypatch.setenv("AGENT_SWARM_ALLOWED_ROOTS", str(tmp_path))
    registry = ToolRegistry.create_default()
    write_tool = registry.get("write_file")

    with pytest.raises(FileAccessDenied):
        write_tool.func(str(tmp_path / ".env.local"), "TOKEN=secret")


def test_graphify_payload_and_export_respect_allowed_roots(monkeypatch, tmp_path):
    monkeypatch.setenv("AGENT_SWARM_ALLOWED_ROOTS", str(tmp_path))
    payload = build_graphify_payload(
        "Agent Swarm",
        nodes=[{"id": "project", "label": "Agent Swarm"}, {"id": "security", "label": "Security", "kind": "safety"}],
        edges=[{"source": "project", "target": "security", "relation": "guards"}],
    )
    target = tmp_path / "graphify.json"

    exported = export_graphify_payload(payload, str(target))

    assert exported == str(target.resolve())
    assert json.loads(target.read_text(encoding="utf-8"))["format"] == "graphify"
    assert payload["edges"][0]["relation"] == "guards"


def test_graphify_project_map_has_agents_and_artifacts():
    payload = build_graphify_project_map("Agent Swarm", agents=["coder", "security"], artifacts=["README.md"])

    labels = {node["label"] for node in payload["nodes"]}
    assert {"Agent Swarm", "coder", "security", "README.md"} <= labels
    assert any(edge["relation"] == "uses_agent" for edge in payload["edges"])


def test_obsidian_vault_and_note_output():
    vault = plan_obsidian_vault("Agent Swarm", ["Architecture", "Security"])
    note = build_obsidian_note("Security", "Review scoped file access.", ["agent swarm", "security"], ["Architecture"])

    assert vault["app"] == "Obsidian"
    assert vault["graph_view"]["backlinks_enabled"] is True
    assert len(vault["notes"]) == 2
    assert "tags: [agent-swarm, security]" in note
    assert "[[Architecture]]" in note


def test_registry_exposes_graphify_and_obsidian_tools():
    tools = set(ToolRegistry.create_default().list_tools())
    expected = {
        "build_graphify_map",
        "build_graphify_project_map",
        "export_graphify_map",
        "plan_obsidian_vault",
        "build_obsidian_note",
        "describe_file_access_policy",
    }
    assert expected <= tools


def test_mcp_marketplace_includes_graphify_and_obsidian():
    knowledge = list_mcp_marketplace(category="Knowledge")
    names = {entry["name"] for entry in knowledge}
    plan = plan_mcp_connectors("connect obsidian graphify notes", limit=5)

    assert {"Obsidian", "Graphify"} <= names
    assert {"Obsidian", "Graphify"} & {entry["name"] for entry in plan["selected"]}


def test_v5_feature_benchmark_covers_graphify_obsidian_file_security(tmp_path):
    results = run_feature_benchmark(SwarmConfig(), output_dir=tmp_path)
    summary = summarize_feature_benchmark(results)
    by_feature = {result.feature: result for result in results}

    assert summary["failures"] == 0
    assert "graphify_obsidian_secure_file_access" in by_feature
    assert by_feature["graphify_obsidian_secure_file_access"].score == 100
