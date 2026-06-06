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
        "voice_transcriber",
        "voice_generator",
        "figma_controller",
        "text_editor",
        "prompt_generator",
        "trading",
        "sales",
        "ai_reviewer",
        "backend_api",
        "frontend_ui",
        "documentation",
        "web_scraper",
        "job_finder",
        "building_designer",
        "animator",
        "hallucination_guard",
        "n8n_workflow_creator",
        "game_developer",
        "social_media_manager",
        "app_tester",
        "app_builder",
        "backend_maker",
        "hermes",
        "auto_learner",
        "test_generator",
        "secret_scanner",
        "playwright_controller",
        "provider_health_monitor",
        "rest_api_wrapper",
    }
    assert required.issubset(agents)
    assert agents["photo_editor"].task_type == "image_generation"
    assert agents["backend_api"].pillar == "code"
    assert agents["frontend_ui"].pillar == "design"
    assert "plan_docs_integration" in agents["documentation"].tools
    assert "compact_context" in agents["coder"].tools
    assert agents["video_editor"].pillar == "see"
    assert agents["voice_transcriber"].task_type == "speech_to_text"
    assert agents["voice_generator"].model_preference == "text_to_speech"
    assert agents["figma_controller"].pillar == "design"
    assert agents["text_editor"].model_preference == "chat"
    assert agents["prompt_generator"].pillar == "design"
    assert "browser_open" in agents["figma_controller"].tools
    assert "browser_snapshot" in agents["testing"].tools
    assert "preflight_review_agent_work" in agents["ai_reviewer"].tools
    assert "plan_temporary_vision" in agents["coder"].tools
    assert "plan_web_scraper" in agents["web_scraper"].tools
    assert "plan_job_finder_applier" in agents["job_finder"].tools
    assert "plan_building_design" in agents["building_designer"].tools
    assert "plan_animation" in agents["animator"].tools
    assert "plan_hallucination_recovery" in agents["hallucination_guard"].tools
    assert "plan_n8n_workflow" in agents["n8n_workflow_creator"].tools
    assert "plan_game_developer" in agents["game_developer"].tools
    assert "plan_social_media_manager" in agents["social_media_manager"].tools
    assert "plan_app_tester" in agents["app_tester"].tools
    assert "plan_app_builder" in agents["app_builder"].tools
    assert "plan_backend_maker" in agents["backend_maker"].tools
    assert "plan_hermes_evolution" in agents["hermes"].tools
    assert "propose_hermes_skill" in agents["hermes"].tools
    assert "persist_hermes_skill" in agents["hermes"].tools
    assert "plan_auto_learner_profile" in agents["auto_learner"].tools
    assert "plan_advanced_capability" in agents["test_generator"].tools


def test_agents_have_model_preferences_and_sub_agent_roles():
    agents = {agent.name: agent for agent in create_specialist_agents()}
    assert agents["coder"].model_preference == "coding"
    assert agents["photo_editor"].model_preference == "image_generation"
    assert agents["video_editor"].model_preference == "video_generation"
    assert agents["voice_transcriber"].model_preference == "speech_to_text"
    assert agents["voice_generator"].model_preference == "text_to_speech"
    assert agents["building_designer"].model_preference == "vision"
    assert agents["animator"].model_preference == "video_generation"
    assert agents["hallucination_guard"].model_preference == "reasoning"
    assert agents["n8n_workflow_creator"].model_preference == "coding"
    assert agents["game_developer"].model_preference == "coding"
    assert agents["social_media_manager"].model_preference == "chat"
    assert agents["app_builder"].model_preference == "coding"
    assert agents["hermes"].model_preference == "reasoning"
    assert agents["auto_learner"].model_preference == "reasoning"
    assert agents["provider_health_monitor"].model_preference == "reasoning"
    assert agents["council_master"].model_preference == "reasoning"
    assert "testing" in agents["hermes"].sub_agent_roles
    assert "checkpoint_manager" in agents["hallucination_guard"].sub_agent_roles
    assert "webhook_listener" in agents["n8n_workflow_creator"].sub_agent_roles
    assert "app_tester" in agents["game_developer"].sub_agent_roles
    assert "marketing" in agents["social_media_manager"].sub_agent_roles
    assert "testing" in agents["coder"].sub_agent_roles
    assert "spawn_agent" in agents["coder"].tools


def test_specialist_mesh_handoffs_include_other_agents():
    agents = create_specialist_agents(mesh=True)
    names = {agent.name for agent in agents}
    for agent in agents:
        assert agent.name not in agent.handoff_targets
        assert set(agent.handoff_targets) == names - {agent.name}
