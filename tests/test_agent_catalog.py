from swarm.agents.catalog import AGENT_SPECS, PILLARS, create_specialist_agents, summarize_catalog


def test_catalog_has_20_plus_agents():
    agents = create_specialist_agents()
    assert len(agents) >= 20
    assert {agent.name for agent in agents} == {spec.name for spec in AGENT_SPECS}


def test_catalog_covers_four_pillars():
    summary = summarize_catalog()
    assert set(summary) == set(PILLARS)
    assert all(summary[pillar] for pillar in PILLARS)


def test_requested_business_and_creative_agents_exist():
    agents = {agent.name: agent for agent in create_specialist_agents()}
    required = {
        "marketing",
        "finance",
        "analytics",
        "ux_research",
        "legal",
        "localization",
        "photo_editor",
        "video_editor",
        "figma_controller",
        "text_editor",
        "prompt_generator",
        "trading",
        "sales",
        "ai_reviewer",
    }
    assert required.issubset(agents)
    assert agents["photo_editor"].task_type == "image_generation"
    assert agents["video_editor"].pillar == "see"
    assert agents["figma_controller"].pillar == "design"
    assert agents["text_editor"].model_preference == "chat"
    assert agents["prompt_generator"].pillar == "design"
    assert "browser_open" in agents["figma_controller"].tools
    assert "browser_snapshot" in agents["testing"].tools
    assert "preflight_review_agent_work" in agents["ai_reviewer"].tools


def test_agents_have_model_preferences_and_sub_agent_roles():
    agents = {agent.name: agent for agent in create_specialist_agents()}
    assert agents["coder"].model_preference == "coding"
    assert agents["photo_editor"].model_preference == "image_generation"
    assert agents["video_editor"].model_preference == "video_generation"
    assert agents["council_master"].model_preference == "reasoning"
    assert "testing" in agents["coder"].sub_agent_roles
    assert "spawn_agent" in agents["coder"].tools


def test_specialist_mesh_handoffs_include_other_agents():
    agents = create_specialist_agents(mesh=True)
    names = {agent.name for agent in agents}
    for agent in agents:
        assert agent.name not in agent.handoff_targets
        assert set(agent.handoff_targets) == names - {agent.name}
