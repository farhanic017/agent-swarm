from swarm.agents.catalog import create_specialist_agents
from swarm.config import ProviderConfig, SwarmConfig
from swarm.core.provider_assignment import (
    assign_distinct_provider_models,
    assign_hybrid_provider_models,
    summarize_hybrid_routes,
)


def make_config() -> SwarmConfig:
    return SwarmConfig(
        providers={
            "google-ai": ProviderConfig(api_key="x", models={"gemini/gemini-2.5-flash": {}}),
            "azure-openai": ProviderConfig(api_key="x", models={"gpt-5.4": {}, "gpt-5.4-mini": {}}),
            "openrouter": ProviderConfig(api_key="x", models={"qwen/qwen3-coder:free": {}}),
            "cloudflare": ProviderConfig(api_key="x", models={"@cf/deepseek-ai/deepseek-r1-distill-qwen-32b": {}}),
        }
    )


def make_hybrid_config() -> SwarmConfig:
    return SwarmConfig(
        providers={
            "ollama": ProviderConfig(api_key="", endpoint="http://localhost:11434/v1", models={"qwen2.5-coder": {}}),
            "mcp-browser": ProviderConfig(api_key="", models={"browser-research": {}}),
            "openclaw": ProviderConfig(api_key="", endpoint="http://localhost:7331/v1", models={"openclaw/director": {}}),
            "azure-openai": ProviderConfig(api_key="x", models={"gpt-5.4": {}, "gpt-5.4-mini": {}}),
            "openrouter": ProviderConfig(api_key="x", models={"nous/hermes-3": {}, "qwen/qwen3-coder:free": {}}),
        }
    )


def test_assigns_distinct_providers_to_agents_and_sub_agents():
    agents = create_specialist_agents()
    assignments = assign_distinct_provider_models(agents, make_config(), include_sub_agents=True, limit=8)
    assert len(assignments) == 8
    assert len({assignment.provider for assignment in assignments[:4]}) == 4
    assert any(assignment.role == "sub_agent" for assignment in assignments)
    assert all(":" in assignment.model_ref for assignment in assignments)
    assert all("/" in assignment.opencode_model for assignment in assignments)
    assert all(assignment.rationale for assignment in assignments)
    assert all(assignment.score > 0 for assignment in assignments)


def test_assignment_returns_empty_without_models():
    cfg = SwarmConfig(providers={"empty": ProviderConfig(api_key="x", models={})})
    assert assign_distinct_provider_models(create_specialist_agents(), cfg) == []


def test_hybrid_assignment_uses_local_mcp_and_cloud_routes():
    assignments = assign_hybrid_provider_models(
        create_specialist_agents(),
        make_hybrid_config(),
        include_sub_agents=True,
    )
    summary = summarize_hybrid_routes(assignments)
    assert summary["local"] > 0
    assert summary["mcp"] > 0
    assert summary["cloud"] > 0
    assert summary["agent_gateway"] > 0
    assert any(item.role == "master" for item in assignments)


def test_core_decision_agents_prefer_reasoning_cloud_over_mcp():
    assignments = assign_hybrid_provider_models(
        create_specialist_agents(),
        make_hybrid_config(),
        include_sub_agents=True,
        limit=4,
    )
    triage = next(item for item in assignments if item.agent_name == "triage" and item.role == "agent")
    assert triage.route_type == "cloud"
    assert triage.provider == "azure-openai"
    assert "reasoning" in triage.rationale


def test_hermes_models_are_ranked_for_chat_and_reasoning():
    agents = [agent for agent in create_specialist_agents() if agent.name in {"writer", "analytics"}]
    assignments = assign_hybrid_provider_models(
        agents,
        SwarmConfig(providers={"openrouter": ProviderConfig(api_key="x", models={"nous/hermes-3": {}})}),
        include_sub_agents=False,
    )
    assert {assignment.agent_name for assignment in assignments} == {"writer", "analytics"}
    assert all(assignment.provider == "openrouter" for assignment in assignments)
    assert all("matches" in assignment.rationale for assignment in assignments)
