from __future__ import annotations

from swarm.config import ProviderConfig, SwarmConfig
from swarm.core.vision_bridge import plan_temporary_vision
from swarm.core.workflow_plans import (
    build_app_builder_plan,
    build_app_tester_plan,
    build_backend_maker_plan,
    build_building_design_plan,
    build_job_finder_applier_plan,
    build_web_scraper_plan,
)
from swarm.tools.registry import ToolRegistry


def test_config_detects_general_vision_models():
    cfg = SwarmConfig(
        providers={
            "openai": ProviderConfig(
                api_key="x",
                models={
                    "gpt-4o": {"modalities": ["vision"]},
                    "gpt-image-1": {"modalities": ["image_generation"]},
                },
            )
        }
    )

    assert cfg.get_best_vision_model() == "openai:gpt-4o"
    assert cfg.find_model("temporary_vision") == "openai:gpt-4o"


def test_temporary_vision_delegates_when_agent_lacks_vision():
    plan = plan_temporary_vision(
        "backend_maker",
        "qwen/qwen3-coder",
        "inspect this UI screenshot and continue building backend validation",
        "image",
        "build",
        "openai:gpt-4o,google:gemini-2.5-flash",
    )

    assert plan["route"] == "delegate_to_temporary_vision_model"
    assert plan["temporary_vision_model"] == "openai:gpt-4o"
    assert "layout" in " ".join(plan["vision_brief_requirements"])
    assert plan["questions"] == []


def test_plan_mode_asks_extensive_questions_only_when_no_vision_exists():
    planning = plan_temporary_vision(
        "designer",
        "mistral-small",
        "plan a building interior and exterior from a missing reference image",
        "image",
        "plan",
        "",
    )
    build = plan_temporary_vision(
        "designer",
        "mistral-small",
        "plan a building interior and exterior from a missing reference image",
        "image",
        "build",
        "",
    )
    simple = plan_temporary_vision("coder", "mistral-small", "make a simple coin in Blender", "design", "plan", "")

    assert planning["route"] == "ask_user_extensive_visual_questions"
    assert len(planning["questions"]) >= 8
    assert build["route"] == "continue_without_annoying_user"
    assert build["questions"] == []
    assert simple["questions"] == []


def test_workflow_planners_cover_requested_features():
    scraper = build_web_scraper_plan("https://example.com/jobs", "collect job cards")
    jobs = build_job_finder_applier_plan("remote python developer", "Python, FastAPI", "find_and_apply")
    building = build_building_design_plan("modern cafe with courtyard")
    tester = build_app_tester_plan("SaaS dashboard")
    builder = build_app_builder_plan("build a CRM")
    backend = build_backend_maker_plan("make auth and billing API", "FastAPI")

    assert scraper["guardrails"]["prefer_official_api"]
    assert jobs["guardrails"]["user_approval_before_submit"]
    assert building["scope"] == "interior_and_exterior"
    assert "accessibility" in tester["test_types"]
    assert "backend_maker" in builder["sub_agents"]
    assert backend["guardrails"]["no_hardcoded_secrets"]


def test_registry_workflow_tools_return_json_strings():
    registry = ToolRegistry.create_default()

    assert "web_scraper" in registry.get("plan_web_scraper").func("https://example.com")
    assert "job_finder_applier" in registry.get("plan_job_finder_applier").func("designer jobs")
    assert "building_interior_exterior_designer" in registry.get("plan_building_design").func("house")
    assert "app_tester" in registry.get("plan_app_tester").func("mobile app")
    assert "app_builder" in registry.get("plan_app_builder").func("todo app")
    assert "backend_maker" in registry.get("plan_backend_maker").func("api")
    assert "delegate_to_temporary_vision_model" in registry.get("plan_temporary_vision").func(
        "coder",
        "qwen-coder",
        "inspect screenshot",
        "image",
        "build",
        "openai:gpt-4o",
    )
