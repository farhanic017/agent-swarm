from pathlib import Path

from swarm.core.environment_support import discover_environment_support
from swarm.core.media_apps import build_mockup_video_plan, build_voice_workflow_plan, list_media_apps
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
    assert "Imagine" in names
    assert "Seedance" in names
    assert "Highfield" in names
    assert "Nano Banana" in names

    plan = build_mockup_video_plan("coffee website mockup")
    assert plan["steps"]
    assert plan["performance_guardrails"]["final_render_requires_user_approval"]

    voice_plan = build_voice_workflow_plan("turn product copy into voiceover", "text_to_speech")
    assert voice_plan["mode"] == "text_to_speech"
    assert voice_plan["performance_guardrails"]["requires_user_approval_for_voice_clone"]


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


def test_default_tool_registry_exposes_new_support_tools():
    tools = set(ToolRegistry.create_default().list_tools())

    assert "preflight_review_agent_work" in tools
    assert "format_pr_inline_comments" in tools
    assert "list_media_app_adapters" in tools
    assert "plan_mockup_video" in tools
    assert "plan_voice_workflow" in tools
    assert "plan_temporary_skills" in tools
    assert "discover_environment_support" in tools
    assert "compact_context" in tools
    assert "plan_docs_integration" in tools
    assert "list_mcp_marketplace" in tools
    assert "plan_mcp_connectors" in tools
