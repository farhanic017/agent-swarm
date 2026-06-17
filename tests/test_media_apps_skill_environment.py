from pathlib import Path

from swarm.core import environment_support
from swarm.core.environment_support import discover_environment_support
from swarm.core.design_policy import classify_3d_design_request
from swarm.core.media_apps import build_3d_modeling_plan, build_animation_plan, build_mockup_video_plan, build_voice_workflow_plan, list_media_apps
from swarm.core.skill_runtime import create_temporary_skill_session, plan_required_skills
from swarm.tools.registry import ToolRegistry


def test_media_app_registry_includes_requested_apps_and_mockup_video():
    apps = list_media_apps()
    names = {app["name"] for app in apps}

    assert "Adobe Photoshop" in names
    assert "Adobe Premiere Pro" in names
    assert "Adobe After Effects" in names
    assert "DaVinci Resolve" in names
    assert "CapCut" in names
    assert "Blender" in names
    assert "ComfyUI" in names
    assert "ElevenLabs" in names
    assert "Manus" in names
    assert "Adobe Audition" in names
    assert "Kling AI" in names
    assert "Google Flow" in names
    assert "Google Veo" in names
    assert "Omni Image/Video" in names
    assert "Recraft" in names
    assert "NVIDIA NIM" in names
    assert "Zyphra" in names
    assert "Hugging Face" in names
    assert "Alibaba DashScope" in names
    assert "Perplexity" in names
    assert "Microsoft Azure AI" in names
    assert "Imagine" in names
    assert "Seedance" in names
    assert "Highfield" in names
    assert "Nano Banana" in names

    plan = build_mockup_video_plan("coffee website mockup")
    assert plan["steps"]
    assert plan["performance_guardrails"]["final_render_requires_user_approval"]

    animation = build_animation_plan("animate an app onboarding flow", "After Effects", "smooth SaaS")
    assert animation["type"] == "animator"
    assert animation["selected_app"]["name"] == "Adobe After Effects"
    assert "keyframes" in " ".join(animation["steps"])
    assert animation["performance_guardrails"]["use_proxy_assets"]

    voice_plan = build_voice_workflow_plan("turn product copy into voiceover", "text_to_speech")
    assert voice_plan["mode"] == "text_to_speech"
    assert voice_plan["performance_guardrails"]["requires_user_approval_for_voice_clone"]


def test_blender_heavy_modeling_mode_is_supported():
    plan = build_3d_modeling_plan(
        "create a heavy highly detailed realistic Blender building with sculpted facade and 4k materials",
        "Blender",
    )

    assert plan["detail_mode"] == "heavy_high_detail"
    assert plan["performance_guardrails"]["heavy_modeling_allowed_after_preview"] is True
    assert plan["performance_guardrails"]["create_proxy_or_decimated_export"] is True
    assert any("high-poly" in step for step in plan["steps"])


def test_temporary_skill_session_installs_and_cleans_up(tmp_path):
    session = create_temporary_skill_session(tmp_path / "skills")
    manifest = session.install_manifest("video-editing", source="test")

    assert Path(manifest["path"]).exists()
    result = session.cleanup()
    assert result["removed"]
    assert not Path(manifest["path"]).exists()


def test_required_skill_planner_and_environment_discovery_are_bounded():
    plan = plan_required_skills("use browser mcp video image blender security voice transcription")

    assert {"browser", "mcp-integration", "video-editing", "image-generation", "blender-automation", "security-review", "voice-generation", "speech-to-text"}.issubset(set(plan["required"]))

    support = discover_environment_support()
    assert {"local_models", "cli_agents", "ide_agents", "mcp_servers"}.issubset(support)


def test_environment_discovery_uses_cli_path_hints(tmp_path, monkeypatch):
    monkeypatch.setattr(environment_support.Path, "home", lambda: tmp_path)
    vibe = tmp_path / "AppData" / "Local" / "Microsoft" / "WinGet" / "Packages" / "MistralAI.MistralVibe.ACP_test"
    windsurf = tmp_path / "AppData" / "Local" / "Programs" / "Windsurf" / "bin"
    aider = tmp_path / ".local" / "bin"
    vibe.mkdir(parents=True)
    windsurf.mkdir(parents=True)
    aider.mkdir(parents=True)
    (vibe / "vibe-acp.exe").write_text("", encoding="utf-8")
    (windsurf / "windsurf.cmd").write_text("", encoding="utf-8")
    (aider / "aider.exe").write_text("", encoding="utf-8")

    support = discover_environment_support()
    clis = {item["name"]: item for item in support["cli_agents"]}

    assert clis["mistral_vibe"]["available"]
    assert clis["aider"]["available"]
    assert clis["windsurf"]["available"]


def test_default_tool_registry_exposes_new_support_tools():
    tools = set(ToolRegistry.create_default().list_tools())

    assert "preflight_review_agent_work" in tools
    assert "format_pr_inline_comments" in tools
    assert "list_media_app_adapters" in tools
    assert "plan_mockup_video" in tools
    assert "plan_animation" in tools
    assert "plan_voice_workflow" in tools
    assert "plan_temporary_skills" in tools
    assert "discover_environment_support" in tools
    assert "compact_context" in tools
    assert "plan_docs_integration" in tools
    assert "list_mcp_marketplace" in tools
    assert "plan_mcp_connectors" in tools
    assert "plan_3d_design_model" in tools
    assert "classify_3d_design_request" in tools
    assert "plan_temporary_vision" in tools
    assert "plan_web_scraper" in tools
    assert "plan_job_finder_applier" in tools
    assert "plan_building_design" in tools
    assert "plan_app_tester" in tools
    assert "plan_app_builder" in tools
    assert "plan_backend_maker" in tools
    assert "plan_hermes_evolution" in tools
    assert "propose_hermes_skill" in tools
    assert "validate_hermes_skill" in tools
    assert "persist_hermes_skill" in tools
    assert "list_hermes_skills" in tools
    assert "list_advanced_capabilities" in tools
    assert "plan_advanced_capability" in tools
    assert "plan_auto_learner_profile" in tools
    assert "plan_swarm_pipeline" in tools


def test_user_owned_designs_are_allowed_for_direct_3d_modeling():
    building = classify_3d_design_request("I designed a building; make my building sketch into a 3D Blender model")
    original_character = classify_3d_design_request("convert my original design creature into a detailed 3D model")
    plan = build_3d_modeling_plan("turn my floor plan and blueprint into a realistic 3D building", "Blender")

    assert building["decision"] == "allow_direct_3d_build"
    assert building["user_owned_design_allowed"] is True
    assert original_character["decision"] == "allow_direct_3d_build"
    assert plan["policy"]["user_owned_design_allowed"] is True
    assert plan["detail_mode"] == "heavy_high_detail"
    assert plan["quality_bar"]["user_owned_designs"] == "match the user's design as closely as possible"


def test_exact_third_party_clone_redirects_to_original_variant():
    result = classify_3d_design_request("make an exact same to same Mewtwo clone")

    assert result["decision"] == "transform_to_original_variant"
    assert result["third_party_exact_clone"] is True
    assert "original variant" in result["guidance"]
