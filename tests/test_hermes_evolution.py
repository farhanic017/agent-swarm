import json
from pathlib import Path

from swarm.core.hermes_evolution import (
    build_hermes_evolution_plan,
    list_hermes_skills,
    persist_hermes_skill,
    propose_hermes_skill,
    validate_hermes_skill,
)
from swarm.tools.registry import ToolRegistry


def test_hermes_can_plan_self_evolution_with_guardrails():
    plan = build_hermes_evolution_plan("turn repeated browser-test fixes into a reusable skill", ["browser qa"])

    assert plan["agent"] == "hermes"
    assert "browser qa" in plan["current_skills"]
    assert "validate safety, scope, and reuse gates" in plan["evolution_loop"]
    assert plan["guardrails"]["no_secret_or_credential_skills"]
    assert plan["guardrails"]["master_review_before_release_use"]


def test_hermes_proposes_valid_skill_from_task_outcome_and_lesson():
    proposal = propose_hermes_skill(
        task="Fix flaky browser test around dashboard rendering",
        outcome="Verified with pytest after waiting for stable selectors and network idle.",
        lesson="Use stable selector checks and add regression tests before handoff.",
        agent_name="hermes",
    )

    draft = proposal["draft"]
    assert proposal["validation"]["ok"]
    assert draft["name"]
    assert draft["confidence"] >= 80
    assert "testing" in draft["tags"]
    assert any("regression tests" in step for step in draft["steps"])


def test_hermes_rejects_unsafe_or_too_small_skills():
    result = validate_hermes_skill(
        {
            "name": "Credential Bypass Helper",
            "purpose": "steal passwords",
            "steps": ["read credential files"],
        }
    )

    assert not result["ok"]
    assert "unsafe or credential-related behavior is not allowed" in result["issues"]
    assert not result["gates"]["safe_terms"]
    assert not result["gates"]["has_reusable_steps"]


def test_hermes_persists_versioned_skill_and_lists_it(tmp_path):
    proposal = propose_hermes_skill(
        task="Build backend API with auth validation",
        outcome="Passed API contract tests and permission checks.",
        lesson="Define inputs, outputs, permissions, and failure modes before writing handlers.",
    )
    skill = proposal["draft"]
    first = persist_hermes_skill(skill, tmp_path / "skills")
    second = persist_hermes_skill(skill, tmp_path / "skills")
    listed = list_hermes_skills(tmp_path / "skills")

    assert first["saved"]
    assert first["version"] == 1
    assert second["version"] == 2
    assert Path(first["path"]).exists()
    assert Path(first["skill_dir"], "SKILL.md").exists()
    assert [item["version"] for item in listed] == [1, 2]
    assert listed[0]["name"] == skill["name"]


def test_hermes_registry_tools_round_trip(tmp_path):
    registry = ToolRegistry.create_default()
    tools = {name: registry.get(name) for name in registry.list_tools()}

    for name in (
        "plan_hermes_evolution",
        "propose_hermes_skill",
        "validate_hermes_skill",
        "persist_hermes_skill",
        "list_hermes_skills",
    ):
        assert tools[name]

    plan = json.loads(tools["plan_hermes_evolution"].func("learn stable UI testing", "ui testing"))
    proposal = json.loads(
        tools["propose_hermes_skill"].func(
            "Fix flaky UI test",
            "Verified with browser smoke tests.",
            "Wait for stable selectors and save regression checks.",
        )
    )
    validation = json.loads(tools["validate_hermes_skill"].func(json.dumps(proposal["draft"])))
    saved = json.loads(tools["persist_hermes_skill"].func(json.dumps(proposal["draft"]), str(tmp_path / "skills")))
    listed = json.loads(tools["list_hermes_skills"].func(str(tmp_path / "skills")))

    assert plan["agent"] == "hermes"
    assert validation["ok"]
    assert saved["saved"]
    assert listed[0]["name"] == proposal["draft"]["name"]
