import json

from swarm.agents.catalog import create_specialist_agents
from swarm.core.advanced_capabilities import (
    build_auto_learner_profile,
    build_swarm_pipeline,
    list_advanced_capabilities,
    plan_advanced_capability,
)
from swarm.tools.registry import ToolRegistry


def test_advanced_capability_directory_covers_requested_categories():
    capabilities = list_advanced_capabilities()
    categories = {item["category"] for item in capabilities}

    assert len(capabilities) >= 55
    assert {
        "core_orchestration",
        "memory_knowledge",
        "code_dev",
        "model_provider",
        "browser_web",
        "security_safety",
        "creative_media",
        "business_act",
        "integrations_ecosystem",
        "observability_monitoring",
        "developer_experience",
    }.issubset(categories)
    assert any(item["key"] == "codex_caching" for item in capabilities)
    assert any(item["key"] == "preference_memory" for item in capabilities)
    assert any(item["key"] == "hallucination_recovery" for item in capabilities)
    assert any(item["key"] == "n8n_workflow_creator" for item in capabilities)
    assert any(item["key"] == "game_developer" for item in capabilities)
    assert any(item["key"] == "social_media_manager" for item in capabilities)


def test_advanced_capability_planner_selects_relevant_agents_and_gates():
    plan = plan_advanced_capability("watch a website and trigger the swarm when pricing changes", "site_monitor")

    assert plan["capability"]["key"] == "site_monitor"
    assert plan["primary_agent"] == "site_monitor"
    assert "web_scraper" in plan["helper_agents"]
    assert "external writes or submissions" in plan["approval_gates"]
    assert "execute only approved actions with scoped tools and checkpoints" in plan["phases"]


def test_new_capability_planner_routes_requested_features():
    hallucination = plan_advanced_capability("fix hallucination and context drift in long sessions", "auto")
    n8n = plan_advanced_capability("create an n8n workflow for launch automation", "auto")
    game = plan_advanced_capability("build a playable browser game", "auto")
    social = plan_advanced_capability("schedule social media posts and manage comments", "auto")

    assert hallucination["primary_agent"] == "hallucination_guard"
    assert n8n["primary_agent"] == "n8n_workflow_creator"
    assert game["primary_agent"] == "game_developer"
    assert social["primary_agent"] == "social_media_manager"


def test_auto_learner_extracts_user_patterns_without_silent_durable_memory():
    profile = build_auto_learner_profile(
        "User keeps asking for aggressive tests, connected graph visuals, fast low-token runs, and README updates.",
        scope="project",
    )

    assert profile["agent"] == "auto_learner"
    assert profile["memory_policy"]["requires_user_approval_for_durable_user_memory"]
    assert "prefers low-lag workflows" in profile["learned_preferences"]
    assert "likes connected graph visualizations" in profile["learned_preferences"]
    assert profile["confidence"] >= 70


def test_swarm_pipeline_plan_marks_parallel_middle_agents():
    pipeline = build_swarm_pipeline("release_review", "triage,security,testing,council_master", "review a PR")

    assert pipeline["name"] == "release_review"
    assert pipeline["execution"]["requires_council_before_start"]
    assert pipeline["execution"]["checkpoint_after_each_agent"]
    assert pipeline["execution"]["parallelizable"] == ["security", "testing"]


def test_registry_exposes_advanced_capability_tools(tmp_path):
    registry = ToolRegistry.create_default()
    tools = {name: registry.get(name) for name in registry.list_tools()}

    for name in (
        "list_advanced_capabilities",
        "plan_advanced_capability",
        "plan_auto_learner_profile",
        "plan_swarm_pipeline",
    ):
        assert tools[name]

    listed = json.loads(tools["list_advanced_capabilities"].func("security_safety"))
    plan = json.loads(tools["plan_advanced_capability"].func("scan outputs for api keys", "secret_scanner"))
    learner = json.loads(tools["plan_auto_learner_profile"].func("dark UI, video demos, README updates", "project"))
    pipeline = json.loads(tools["plan_swarm_pipeline"].func("ship", "triage,coder,testing", "build and test"))

    assert listed[0]["category"] == "security_safety"
    assert plan["capability"]["key"] == "secret_scanner"
    assert learner["memory_policy"]["requires_user_approval_for_durable_user_memory"]
    assert pipeline["agents"] == ["triage", "coder", "testing"]


def test_new_specialist_agents_are_available():
    agents = {agent.name: agent for agent in create_specialist_agents(mesh=False)}
    required = {
        "checkpoint_manager",
        "replay_runner",
        "priority_scheduler",
        "pipeline_manager",
        "vector_memory",
        "auto_learner",
        "knowledge_graph",
        "semantic_run_search",
        "codex_cache",
        "test_generator",
        "migration_agent",
        "dependency_auditor",
        "code_explainer",
        "refactor_planner",
        "ci_cd_generator",
        "dynamic_benchmark",
        "model_trainer",
        "cost_optimizer",
        "quantization_planner",
        "provider_health_monitor",
        "playwright_controller",
        "form_filler",
        "site_monitor",
        "api_explorer",
        "link_validator",
        "secret_scanner",
        "cve_monitor",
        "sandbox_manager",
        "diff_reviewer",
        "permission_escalation_monitor",
        "storyboard",
        "brand_consistency",
        "i18n_pipeline",
        "music_audio",
        "ar_vr_planner",
        "competitor_analysis",
        "seo_audit",
        "analytics_interpreter",
        "email_campaign",
        "invoice_contract",
        "pitch_deck",
        "github_actions_runner",
        "webhook_listener",
        "chatops_bot",
        "notion_sync",
        "issue_tracker",
        "supabase_agent",
        "stripe_agent",
        "docker_agent",
        "telemetry_tracer",
        "cost_dashboard",
        "performance_leaderboard",
        "run_diff_viewer",
        "anomaly_detector",
        "vscode_extension",
        "swarm_builder_ui",
        "agent_marketplace",
        "cloud_deploy",
        "typescript_sdk",
        "rest_api_wrapper",
        "hallucination_guard",
        "n8n_workflow_creator",
        "game_developer",
        "social_media_manager",
    }

    assert required.issubset(agents)
    assert agents["auto_learner"].pillar == "act"
    assert agents["test_generator"].model_preference == "coding"
    assert agents["brand_consistency"].model_preference == "vision"
    assert agents["hallucination_guard"].model_preference == "reasoning"
    assert agents["n8n_workflow_creator"].model_preference == "coding"
    assert agents["game_developer"].model_preference == "coding"
    assert agents["social_media_manager"].model_preference == "chat"
    assert "plan_advanced_capability" in agents["secret_scanner"].tools
