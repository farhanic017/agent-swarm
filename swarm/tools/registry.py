from __future__ import annotations
import json
import datetime
from typing import Optional, Callable

from swarm.core.state import SharedState
from swarm.tools.base import Tool
from swarm.tools.terminal import TerminalTools
from swarm.tools.react_doctor import ReactDoctorTool
from swarm.tools.graph import graph_search, graph_neighbors, graph_path, graph_explain, graph_stats
from swarm.core.messaging import MessageHub
from swarm.core.brainstorm import BrainstormEngine
from swarm.core.debug_collab import DebugCollaboration
from swarm.core.learning import LessonLearner
from swarm.core.context import build_compaction_summary, format_compaction_summary
from swarm.core.advanced_capabilities import (
    build_auto_learner_profile,
    build_swarm_pipeline,
    list_advanced_capabilities,
    plan_advanced_capability,
)
from swarm.core.docs_integration import plan_docs_for_task
from swarm.core.file_access import describe_file_access_policy, secure_list_directory, secure_read_file, secure_write_file
from swarm.core.graphify import build_graphify_payload, build_graphify_project_map, export_graphify_payload
from swarm.core.hermes_evolution import (
    build_hermes_evolution_plan,
    list_hermes_skills,
    persist_hermes_skill,
    propose_hermes_skill,
    validate_hermes_skill,
)
from swarm.core.mcp_marketplace import list_mcp_marketplace, plan_mcp_connectors
from swarm.core.obsidian import build_obsidian_note, plan_obsidian_vault
from swarm.core.preflight_review import review_agent_output, format_github_review_comments
from swarm.core.design_policy import classify_3d_design_request
from swarm.core.media_apps import list_media_apps, build_mockup_video_plan, build_voice_workflow_plan, build_3d_modeling_plan, build_animation_plan
from swarm.core.skill_runtime import plan_required_skills
from swarm.core.environment_support import discover_environment_support
from swarm.core.vision_bridge import plan_temporary_vision
from swarm.core.workflow_plans import (
    build_app_builder_plan,
    build_app_tester_plan,
    build_backend_maker_plan,
    build_building_design_plan,
    build_game_developer_plan,
    build_hallucination_recovery_plan,
    build_job_finder_applier_plan,
    build_n8n_workflow_plan,
    build_social_media_manager_plan,
    build_web_scraper_plan,
)
from swarm.tools.finance import FINANCE_TOOL_DEFINITIONS
from swarm.core.shared_memory import SHARED_MEMORY_TOOL_DEFINITIONS
from swarm.core.system_awareness import SYSTEM_AWARENESS_TOOL_DEFINITIONS


class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool):
        self._tools[tool.name] = tool

    def register_func(self, name: str, description: str, func: Callable, parameters: dict):
        self._tools[name] = Tool(
            name=name,
            description=description,
            func=func,
            parameters=parameters,
        )

    def get(self, name: str) -> Optional[Tool]:
        return self._tools.get(name)

    def get_tools_for_agent(self, agent_name: str, agent_tools: list[str]) -> list[Tool]:
        found = []
        for t in agent_tools:
            if t in self._tools:
                found.append(self._tools[t])
        return found

    def to_openai_format(self, tool_names: list[str]) -> list[dict]:
        return [
            self._tools[t].to_openai_format()
            for t in tool_names
            if t in self._tools
        ]

    def list_tools(self) -> list[str]:
        return list(self._tools.keys())

    def merge(self, other: ToolRegistry):
        self._tools.update(other._tools)

    @classmethod
    def create_default(cls) -> ToolRegistry:
        registry = cls()

        registry.register(Tool(
            name="get_current_time",
            description="Get the current date and time",
            func=lambda: datetime.datetime.now().isoformat(),
            parameters={"type": "object", "properties": {}, "required": []},
        ))

        registry.register(Tool(
            name="read_file",
            description="Read a file only when it is inside AGENT_SWARM_ALLOWED_ROOTS or the current working directory and is not a sensitive credential path.",
            func=secure_read_file,
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Absolute path to the file"},
                },
                "required": ["path"],
            },
        ))

        registry.register(Tool(
            name="write_file",
            description="Write a file only when it is inside AGENT_SWARM_ALLOWED_ROOTS or the current working directory and is not a sensitive credential path.",
            func=secure_write_file,
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Absolute path to the file"},
                    "content": {"type": "string", "description": "Content to write"},
                },
                "required": ["path", "content"],
            },
        ))

        registry.register(Tool(
            name="list_directory",
            description="List a directory only when it is inside AGENT_SWARM_ALLOWED_ROOTS or the current working directory and is not a sensitive credential path.",
            func=secure_list_directory,
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Directory path"},
                },
                "required": ["path"],
            },
        ))

        registry.register(Tool(
            name="search_web",
            description="Search the web for information. Returns formatted results.",
            func=lambda query: f"[Web search results for: {query}]",
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                },
                "required": ["query"],
            },
        ))

        registry.register(Tool(
            name="run_python",
            description="Execute Python code and return the result. Use for calculations and data processing.",
            func=lambda code: (lambda: (exec(code), "Code executed successfully")[1])(),
            parameters={
                "type": "object",
                "properties": {
                    "code": {"type": "string", "description": "Python code to execute"},
                },
                "required": ["code"],
            },
        ))

        registry.register(Tool(
            name="save_artifact",
            description="Save an artifact (file, data, result) to the shared state",
            func=lambda key, value: json.dumps({"key": key, "value": value[:200] if isinstance(value, str) else value}),
            parameters={
                "type": "object",
                "properties": {
                    "key": {"type": "string", "description": "Artifact identifier"},
                    "value": {"type": "string", "description": "Artifact content"},
                },
                "required": ["key", "value"],
            },
        ))

        registry._register_terminal_tools()
        registry._register_react_doctor_tool()
        registry._register_mcp_tool_stubs()
        registry._register_graph_tools()
        registry._register_browser_tools()
        registry._register_preflight_review_tools()
        registry._register_media_app_tools()
        registry._register_workflow_planner_tools()
        registry._register_hermes_evolution_tools()
        registry._register_advanced_capability_tools()
        registry._register_environment_tools()
        registry._register_knowledge_app_tools()
        registry._register_context_docs_mcp_tools()
        registry._register_finance_tools()
        registry._register_shared_memory_tools()
        registry._register_system_awareness_tools()

        return registry

    def inject_collaboration_refs(self, message_hub: MessageHub,
                                   brainstorm_engine: BrainstormEngine,
                                   debug_collab: DebugCollaboration,
                                   lesson_learner: LessonLearner):
        """Inject collaboration tools that reference shared instances."""
        self._register_message_tools(message_hub)
        self._register_brainstorm_tools(brainstorm_engine)
        self._register_debug_tools(debug_collab)
        self._register_lesson_tools(lesson_learner)

    def _register_terminal_tools(self):
        _tt = TerminalTools()

        async def _run_command(command: str, timeout: int = 30, workdir: str = None):
            return await _tt.run_command(command, timeout, workdir)

        async def _run_script(code: str, language: str = "python", timeout: int = 60):
            return await _tt.run_script(code, language, timeout)

        self.register(Tool(
            name="run_command",
            description="Execute a shell command (bash/sh/cmd/powershell). Returns stdout + stderr + exit code. Use for file operations, git, builds, and terminal tasks.",
            func=_run_command,
            parameters={
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "Shell command to execute"},
                    "timeout": {"type": "integer", "description": "Timeout in seconds (default 30)"},
                    "workdir": {"type": "string", "description": "Working directory (optional)"},
                },
                "required": ["command"],
            },
        ))

        self.register(Tool(
            name="run_script",
            description="Write and execute a script in any language (python, bash, javascript, ruby, etc.). Creates a temp file, runs it, returns output.",
            func=_run_script,
            parameters={
                "type": "object",
                "properties": {
                    "code": {"type": "string", "description": "Script source code"},
                    "language": {"type": "string", "description": "Language (python, bash, javascript, ruby, etc.)"},
                    "timeout": {"type": "integer", "description": "Timeout in seconds (default 60)"},
                },
                "required": ["code", "language"],
            },
        ))

    def _register_react_doctor_tool(self):
        _rd = ReactDoctorTool()

        async def _scan(directory: str = ".", verbose: bool = False, score_only: bool = False, diff: str = None, timeout: int = 120):
            return await _rd.scan(directory, verbose, score_only, diff, timeout)

        async def _install(directory: str = "."):
            return await _rd.install_skill(directory)

        self.register(Tool(
            name="run_react_doctor",
            description="Scan a React project for state/effects, performance, architecture, security, and accessibility issues using React Doctor. Returns a 0-100 health score with diagnostics. Use on any React/Next.js/Vite/React Native project.",
            func=_scan,
            parameters={
                "type": "object",
                "properties": {
                    "directory": {"type": "string", "description": "Path to the React project root (default: current directory)"},
                    "verbose": {"type": "boolean", "description": "Show affected files and line numbers per rule (default: false)"},
                    "score_only": {"type": "boolean", "description": "Return only the numeric 0-100 score (default: false)"},
                    "diff": {"type": "string", "description": "Base branch for diff mode — only scan files changed vs this branch"},
                    "timeout": {"type": "integer", "description": "Max seconds to wait for scan (default: 120)"},
                },
                "required": [],
            },
        ))

        self.register(Tool(
            name="react_doctor_install_skill",
            description="Install the React Doctor best-practices skill into a project so coding agents (Cursor, Claude Code, OpenCode, etc.) learn to avoid bad React patterns.",
            func=_install,
            parameters={
                "type": "object",
                "properties": {
                    "directory": {"type": "string", "description": "Project root to install the skill into (default: current directory)"},
                },
                "required": [],
            },
        ))

    def _register_browser_tools(self):
        _tt = TerminalTools()

        async def _browser_open(url: str, mode: str = "local"):
            flag = "--local" if mode == "local" else "--remote" if mode == "remote" else "--auto-connect"
            return await _tt.run_command(f'browse open "{url}" {flag}', timeout=60)

        async def _browser_snapshot():
            return await _tt.run_command("browse snapshot", timeout=60)

        async def _browser_click(ref: str):
            return await _tt.run_command(f"browse click {ref}", timeout=30)

        async def _browser_get_title():
            return await _tt.run_command("browse get title", timeout=30)

        async def _browser_stop():
            return await _tt.run_command("browse stop", timeout=30)

        self.register(Tool(
            name="browser_open",
            description="Open a URL in a controllable browser session using the browse CLI.",
            func=_browser_open,
            parameters={
                "type": "object",
                "properties": {
                    "url": {"type": "string"},
                    "mode": {"type": "string", "enum": ["local", "remote", "auto"], "description": "Browser mode"},
                },
                "required": ["url"],
            },
        ))
        self.register(Tool(
            name="browser_snapshot",
            description="Return the current browser accessibility tree with interaction refs.",
            func=_browser_snapshot,
            parameters={"type": "object", "properties": {}, "required": []},
        ))
        self.register(Tool(
            name="browser_click",
            description="Click an element by ref from browser_snapshot, for example @0-5.",
            func=_browser_click,
            parameters={
                "type": "object",
                "properties": {"ref": {"type": "string"}},
                "required": ["ref"],
            },
        ))
        self.register(Tool(
            name="browser_get_title",
            description="Get the active browser page title.",
            func=_browser_get_title,
            parameters={"type": "object", "properties": {}, "required": []},
        ))
        self.register(Tool(
            name="browser_stop",
            description="Stop the browser automation session.",
            func=_browser_stop,
            parameters={"type": "object", "properties": {}, "required": []},
        ))

    def _register_mcp_tool_stubs(self):
        async def _mcp_list_tools():
            return "Available MCP tools: Use 'mcp_call' to invoke a connected MCP tool."

        async def _mcp_call(server: str = "", tool: str = "", arguments: str = "{}"):
            return f"MCP call to {server}/{tool} with {arguments}. Ensure MCP servers are connected via config."

        self.register(Tool(
            name="mcp_list_tools",
            description="List all available tools from connected MCP servers",
            func=_mcp_list_tools,
            parameters={"type": "object", "properties": {}, "required": []},
        ))

        self.register(Tool(
            name="mcp_call",
            description="Call a tool on a connected MCP server. Use server='server_name' and tool='tool_name' with JSON arguments.",
            func=_mcp_call,
            parameters={
                "type": "object",
                "properties": {
                    "server": {"type": "string", "description": "MCP server name (e.g., 'filesystem', 'github')"},
                    "tool": {"type": "string", "description": "Tool name on the MCP server"},
                    "arguments": {"type": "string", "description": "JSON object of arguments"},
                },
                "required": ["server", "tool"],
            },
        ))

    def _register_preflight_review_tools(self):
        def _review(agent_name: str, output: str, path: str = "agent-output.md"):
            return json.dumps(review_agent_output(agent_name, output, path).to_dict(), indent=2)

        def _comments(agent_name: str, output: str, path: str = "agent-output.md", commit_id: str = ""):
            result = review_agent_output(agent_name, output, path)
            return json.dumps(format_github_review_comments(result, commit_id), indent=2)

        self.register(Tool(
            name="preflight_review_agent_work",
            description="Review one agent's work for security vulnerabilities, performance issues, and logic errors before integration.",
            func=_review,
            parameters={
                "type": "object",
                "properties": {
                    "agent_name": {"type": "string"},
                    "output": {"type": "string"},
                    "path": {"type": "string"},
                },
                "required": ["agent_name", "output"],
            },
        ))
        self.register(Tool(
            name="format_pr_inline_comments",
            description="Convert a preflight review into GitHub pull request inline comment payloads.",
            func=_comments,
            parameters={
                "type": "object",
                "properties": {
                    "agent_name": {"type": "string"},
                    "output": {"type": "string"},
                    "path": {"type": "string"},
                    "commit_id": {"type": "string"},
                },
                "required": ["agent_name", "output"],
            },
        ))

    def _register_media_app_tools(self):
        self.register(Tool(
            name="list_media_app_adapters",
            description="List supported photo, video, mockup, Adobe, DaVinci Resolve, CapCut, Figma, Blender, and AI media app adapters.",
            func=lambda category=None: json.dumps(list_media_apps(category), indent=2),
            parameters={
                "type": "object",
                "properties": {"category": {"type": "string"}},
                "required": [],
            },
        ))
        self.register(Tool(
            name="plan_mockup_video",
            description="Create a lightweight mockup video workflow using supported video, motion, 3D, or AI media apps.",
            func=lambda prompt, app="auto": json.dumps(build_mockup_video_plan(prompt, app), indent=2),
            parameters={
                "type": "object",
                "properties": {
                    "prompt": {"type": "string"},
                    "app": {"type": "string"},
                },
                "required": ["prompt"],
            },
        ))
        self.register(Tool(
            name="plan_animation",
            description="Plan 2D, 3D, UI, product, logo, character, mockup, or video animation with storyboard, timing, keyframes, render preview, and export QA.",
            func=lambda prompt, app="auto", style="auto": json.dumps(build_animation_plan(prompt, app, style), indent=2),
            parameters={
                "type": "object",
                "properties": {
                    "prompt": {"type": "string"},
                    "app": {"type": "string"},
                    "style": {"type": "string"},
                },
                "required": ["prompt"],
            },
        ))
        self.register(Tool(
            name="plan_3d_design_model",
            description="Plan a 3D model from a user-owned design, sketch, building, product, CAD note, or original character reference. Allows faithful user-owned designs and only redirects exact third-party clones to original variants.",
            func=lambda prompt, app="Blender": json.dumps(build_3d_modeling_plan(prompt, app), indent=2),
            parameters={
                "type": "object",
                "properties": {
                    "prompt": {"type": "string"},
                    "app": {"type": "string"},
                },
                "required": ["prompt"],
            },
        ))
        self.register(Tool(
            name="classify_3d_design_request",
            description="Classify whether a 3D design request is a user-owned design that can be built directly or an exact third-party clone that should become an original variant.",
            func=lambda prompt: json.dumps(classify_3d_design_request(prompt), indent=2),
            parameters={
                "type": "object",
                "properties": {"prompt": {"type": "string"}},
                "required": ["prompt"],
            },
        ))
        self.register(Tool(
            name="plan_voice_workflow",
            description="Create a speech-to-text or text-to-speech workflow using built-in audio providers such as ElevenLabs, Whisper/OpenAI-compatible routes, or Manus task routing.",
            func=lambda prompt, mode="speech_to_text", provider="auto": json.dumps(build_voice_workflow_plan(prompt, mode, provider), indent=2),
            parameters={
                "type": "object",
                "properties": {
                    "prompt": {"type": "string"},
                    "mode": {"type": "string", "enum": ["speech_to_text", "text_to_speech", "tts", "voice_generation"]},
                    "provider": {"type": "string"},
                },
                "required": ["prompt"],
            },
        ))

    def _register_workflow_planner_tools(self):
        self.register(Tool(
            name="plan_temporary_vision",
            description="Let any non-vision agent get a one-time detailed image/video/design/layout/animation brief from a vision model, or ask detailed questions only in plan mode when no vision model exists.",
            func=lambda agent_name, agent_model, task, asset_type="image_or_video", mode="build", available_vision_models="": json.dumps(
                plan_temporary_vision(agent_name, agent_model, task, asset_type, mode, available_vision_models),
                indent=2,
            ),
            parameters={
                "type": "object",
                "properties": {
                    "agent_name": {"type": "string"},
                    "agent_model": {"type": "string"},
                    "task": {"type": "string"},
                    "asset_type": {"type": "string"},
                    "mode": {"type": "string", "enum": ["plan", "build", "normal"]},
                    "available_vision_models": {"type": "string", "description": "Comma-separated or JSON list of vision-capable model refs"},
                },
                "required": ["agent_name", "agent_model", "task"],
            },
        ))
        self.register(Tool(
            name="plan_web_scraper",
            description="Plan a compliant web scraper with browser/API fallback, extraction fields, rate limits, source tracking, and export strategy.",
            func=lambda target, goal="extract useful data": json.dumps(build_web_scraper_plan(target, goal), indent=2),
            parameters={
                "type": "object",
                "properties": {"target": {"type": "string"}, "goal": {"type": "string"}},
                "required": ["target"],
            },
        ))
        self.register(Tool(
            name="plan_job_finder_applier",
            description="Plan job search, fit scoring, tailored application drafts, and user-approved job application submission.",
            func=lambda query, profile_summary="", mode="find": json.dumps(build_job_finder_applier_plan(query, profile_summary, mode), indent=2),
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "profile_summary": {"type": "string"},
                    "mode": {"type": "string", "enum": ["find", "apply", "find_and_apply"]},
                },
                "required": ["query"],
            },
        ))
        self.register(Tool(
            name="plan_building_design",
            description="Plan building interior and exterior design with facade, room layout, lighting, materials, circulation, and 3D handoff.",
            func=lambda prompt, scope="interior_and_exterior": json.dumps(build_building_design_plan(prompt, scope), indent=2),
            parameters={
                "type": "object",
                "properties": {"prompt": {"type": "string"}, "scope": {"type": "string"}},
                "required": ["prompt"],
            },
        ))
        self.register(Tool(
            name="plan_app_tester",
            description="Plan full app testing across unit, integration, browser, accessibility, responsive, performance, and security-smoke checks.",
            func=lambda app, focus="full QA": json.dumps(build_app_tester_plan(app, focus), indent=2),
            parameters={
                "type": "object",
                "properties": {"app": {"type": "string"}, "focus": {"type": "string"}},
                "required": ["app"],
            },
        ))
        self.register(Tool(
            name="plan_app_builder",
            description="Plan app building from requirements through frontend, backend, tests, integration, docs, and master review.",
            func=lambda prompt, stack="auto": json.dumps(build_app_builder_plan(prompt, stack), indent=2),
            parameters={
                "type": "object",
                "properties": {"prompt": {"type": "string"}, "stack": {"type": "string"}},
                "required": ["prompt"],
            },
        ))
        self.register(Tool(
            name="plan_backend_maker",
            description="Plan backend/API creation with schemas, auth, validation, permissions, tests, docs, and security guardrails.",
            func=lambda prompt, framework="auto": json.dumps(build_backend_maker_plan(prompt, framework), indent=2),
            parameters={
                "type": "object",
                "properties": {"prompt": {"type": "string"}, "framework": {"type": "string"}},
                "required": ["prompt"],
            },
        ))
        self.register(Tool(
            name="plan_hallucination_recovery",
            description="Plan long-session hallucination recovery with compaction, evidence pinning, assumption checks, and replacement-model memory.",
            func=lambda session_summary, mode="long_session": json.dumps(
                build_hallucination_recovery_plan(session_summary, mode),
                indent=2,
            ),
            parameters={
                "type": "object",
                "properties": {"session_summary": {"type": "string"}, "mode": {"type": "string"}},
                "required": ["session_summary"],
            },
        ))
        self.register(Tool(
            name="plan_n8n_workflow",
            description="Plan an n8n automation workflow with nodes, credentials, dry-run payloads, retries, schedules, and approval gates.",
            func=lambda prompt, trigger="manual": json.dumps(build_n8n_workflow_plan(prompt, trigger), indent=2),
            parameters={
                "type": "object",
                "properties": {"prompt": {"type": "string"}, "trigger": {"type": "string"}},
                "required": ["prompt"],
            },
        ))
        self.register(Tool(
            name="plan_game_developer",
            description="Plan a playable game build with engine choice, core loop, controls, assets, testing, and export checks.",
            func=lambda prompt, engine="auto": json.dumps(build_game_developer_plan(prompt, engine), indent=2),
            parameters={
                "type": "object",
                "properties": {"prompt": {"type": "string"}, "engine": {"type": "string"}},
                "required": ["prompt"],
            },
        ))
        self.register(Tool(
            name="plan_social_media_manager",
            description="Plan social media posting and management with drafts, creative prompts, approvals, scheduling, comments, and analytics.",
            func=lambda prompt, platforms="auto": json.dumps(build_social_media_manager_plan(prompt, platforms), indent=2),
            parameters={
                "type": "object",
                "properties": {"prompt": {"type": "string"}, "platforms": {"type": "string"}},
                "required": ["prompt"],
            },
        ))

    def _register_hermes_evolution_tools(self):
        self.register(Tool(
            name="plan_hermes_evolution",
            description="Plan Hermes-style self-evolution: observe reusable patterns, propose skills, validate safety gates, version manifests, and reuse approved skills.",
            func=lambda task, current_skills="": json.dumps(
                build_hermes_evolution_plan(task, [item.strip() for item in current_skills.split(",") if item.strip()]),
                indent=2,
            ),
            parameters={
                "type": "object",
                "properties": {
                    "task": {"type": "string"},
                    "current_skills": {"type": "string", "description": "Comma-separated existing skill names"},
                },
                "required": ["task"],
            },
        ))
        self.register(Tool(
            name="propose_hermes_skill",
            description="Create a candidate reusable skill from a task, outcome, and lesson learned.",
            func=lambda task, outcome, lesson, agent_name="hermes": json.dumps(
                propose_hermes_skill(task, outcome, lesson, agent_name),
                indent=2,
            ),
            parameters={
                "type": "object",
                "properties": {
                    "task": {"type": "string"},
                    "outcome": {"type": "string"},
                    "lesson": {"type": "string"},
                    "agent_name": {"type": "string"},
                },
                "required": ["task", "outcome", "lesson"],
            },
        ))
        self.register(Tool(
            name="validate_hermes_skill",
            description="Validate a Hermes evolved skill JSON manifest for safety, reuse, and bounded size.",
            func=lambda skill_json: json.dumps(validate_hermes_skill(json.loads(skill_json)), indent=2),
            parameters={
                "type": "object",
                "properties": {"skill_json": {"type": "string"}},
                "required": ["skill_json"],
            },
        ))
        self.register(Tool(
            name="persist_hermes_skill",
            description="Persist a validated Hermes skill JSON manifest as versioned files under a scoped skill root.",
            func=lambda skill_json, root=".swarm_evolved_skills": json.dumps(persist_hermes_skill(json.loads(skill_json), root), indent=2),
            parameters={
                "type": "object",
                "properties": {
                    "skill_json": {"type": "string"},
                    "root": {"type": "string"},
                },
                "required": ["skill_json"],
            },
        ))
        self.register(Tool(
            name="list_hermes_skills",
            description="List persisted Hermes evolved skills and versions.",
            func=lambda root=".swarm_evolved_skills": json.dumps(list_hermes_skills(root), indent=2),
            parameters={
                "type": "object",
                "properties": {"root": {"type": "string"}},
                "required": [],
            },
        ))

    def _register_advanced_capability_tools(self):
        self.register(Tool(
            name="list_advanced_capabilities",
            description="List advanced Agent Swarm capabilities across orchestration, memory, dev, model/provider, browser/web, security, creative, business, integrations, observability, and developer experience.",
            func=lambda category=None: json.dumps(list_advanced_capabilities(category), indent=2),
            parameters={
                "type": "object",
                "properties": {"category": {"type": "string"}},
                "required": [],
            },
        ))
        self.register(Tool(
            name="plan_advanced_capability",
            description="Create a scoped implementation or run plan for an advanced Agent Swarm capability.",
            func=lambda task, capability="auto": json.dumps(plan_advanced_capability(task, capability), indent=2),
            parameters={
                "type": "object",
                "properties": {
                    "task": {"type": "string"},
                    "capability": {"type": "string"},
                },
                "required": ["task"],
            },
        ))
        self.register(Tool(
            name="plan_auto_learner_profile",
            description="Infer project-scoped user preferences, coding style, visual taste, and workflow patterns from provided events without storing durable user memory unless approved.",
            func=lambda events, scope="project": json.dumps(build_auto_learner_profile(events, scope), indent=2),
            parameters={
                "type": "object",
                "properties": {
                    "events": {"type": "string"},
                    "scope": {"type": "string"},
                },
                "required": ["events"],
            },
        ))
        self.register(Tool(
            name="plan_swarm_pipeline",
            description="Build a named reusable swarm pipeline from a comma-separated agent chain and goal.",
            func=lambda name, agents, goal: json.dumps(build_swarm_pipeline(name, agents, goal), indent=2),
            parameters={
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "agents": {"type": "string"},
                    "goal": {"type": "string"},
                },
                "required": ["name", "agents", "goal"],
            },
        ))

    def _register_environment_tools(self):
        self.register(Tool(
            name="plan_temporary_skills",
            description="Plan temporary skills to download/use for a task, with cleanup after agents finish.",
            func=lambda task, existing_skills="": json.dumps(
                plan_required_skills(task, [s.strip() for s in existing_skills.split(",") if s.strip()]),
                indent=2,
            ),
            parameters={
                "type": "object",
                "properties": {
                    "task": {"type": "string"},
                    "existing_skills": {"type": "string"},
                },
                "required": ["task"],
            },
        ))
        self.register(Tool(
            name="discover_environment_support",
            description="Detect local model runtimes, CLI agents, IDE agents, and common MCP support without blocking on unavailable tools.",
            func=lambda: json.dumps(discover_environment_support(), indent=2),
            parameters={"type": "object", "properties": {}, "required": []},
        ))

    def _register_knowledge_app_tools(self):
        self.register(Tool(
            name="describe_file_access_policy",
            description="Show the scoped file-access policy that prevents agents from reading or writing files outside allowed project roots.",
            func=lambda: json.dumps(describe_file_access_policy(), indent=2),
            parameters={"type": "object", "properties": {}, "required": []},
        ))
        self.register(Tool(
            name="build_graphify_map",
            description="Build an in-memory Graphify-compatible graph payload from a title, nodes, and edges.",
            func=lambda title, nodes=None, edges=None: json.dumps(
                build_graphify_payload(
                    title,
                    json.loads(nodes) if isinstance(nodes, str) and nodes.strip() else None,
                    json.loads(edges) if isinstance(edges, str) and edges.strip() else None,
                ),
                indent=2,
            ),
            parameters={
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "nodes": {"type": "string", "description": "Optional JSON array of node objects"},
                    "edges": {"type": "string", "description": "Optional JSON array of edge objects"},
                },
                "required": ["title"],
            },
        ))
        self.register(Tool(
            name="build_graphify_project_map",
            description="Build a Graphify project map linking a project to agents and artifacts.",
            func=lambda project, agents="", artifacts="": json.dumps(
                build_graphify_project_map(
                    project,
                    [item.strip() for item in agents.split(",") if item.strip()],
                    [item.strip() for item in artifacts.split(",") if item.strip()],
                ),
                indent=2,
            ),
            parameters={
                "type": "object",
                "properties": {
                    "project": {"type": "string"},
                    "agents": {"type": "string", "description": "Comma-separated agent names"},
                    "artifacts": {"type": "string", "description": "Comma-separated artifact names"},
                },
                "required": ["project"],
            },
        ))
        self.register(Tool(
            name="export_graphify_map",
            description="Export a Graphify JSON payload to an allowed project path.",
            func=lambda payload, path: export_graphify_payload(json.loads(payload), path),
            parameters={
                "type": "object",
                "properties": {
                    "payload": {"type": "string", "description": "Graphify JSON payload"},
                    "path": {"type": "string"},
                },
                "required": ["payload", "path"],
            },
        ))
        self.register(Tool(
            name="plan_obsidian_vault",
            description="Plan an Obsidian markdown vault with backlinks, graph-view clusters, and project notes.",
            func=lambda project, topics="": json.dumps(
                plan_obsidian_vault(project, [item.strip() for item in topics.split(",") if item.strip()]),
                indent=2,
            ),
            parameters={
                "type": "object",
                "properties": {
                    "project": {"type": "string"},
                    "topics": {"type": "string", "description": "Comma-separated note topics"},
                },
                "required": ["project"],
            },
        ))
        self.register(Tool(
            name="build_obsidian_note",
            description="Build a markdown note with Obsidian-compatible frontmatter, tags, and wikilinks.",
            func=lambda title, body, tags="", links="": build_obsidian_note(
                title,
                body,
                [item.strip() for item in tags.split(",") if item.strip()],
                [item.strip() for item in links.split(",") if item.strip()],
            ),
            parameters={
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "body": {"type": "string"},
                    "tags": {"type": "string", "description": "Comma-separated tags"},
                    "links": {"type": "string", "description": "Comma-separated Obsidian note links"},
                },
                "required": ["title", "body"],
            },
        ))

    def _register_context_docs_mcp_tools(self):
        def _compact_context(task: str, summary: str = "", pending: str = "", project_tree: str = ""):
            state = SharedState(user_input=task, summary=summary)
            pending_items = [item.strip() for item in pending.split("\n") if item.strip()]
            compact = build_compaction_summary(state, project_tree=project_tree, pending=pending_items)
            return format_compaction_summary(compact)

        self.register(Tool(
            name="compact_context",
            description="Create a /compact summary preserving architecture, completed work, pending work, decisions, risks, and next-agent instructions.",
            func=_compact_context,
            parameters={
                "type": "object",
                "properties": {
                    "task": {"type": "string"},
                    "summary": {"type": "string"},
                    "pending": {"type": "string", "description": "Newline-separated pending items"},
                    "project_tree": {"type": "string"},
                },
                "required": ["task"],
            },
        ))
        self.register(Tool(
            name="plan_docs_integration",
            description="Select framework/API documentation sources agents should consult before generating code.",
            func=lambda task: json.dumps(plan_docs_for_task(task), indent=2),
            parameters={
                "type": "object",
                "properties": {"task": {"type": "string"}},
                "required": ["task"],
            },
        ))
        self.register(Tool(
            name="list_mcp_marketplace",
            description="List supported MCP marketplace connectors by category or search query.",
            func=lambda category=None, query=None: json.dumps(list_mcp_marketplace(category, query), indent=2),
            parameters={
                "type": "object",
                "properties": {
                    "category": {"type": "string"},
                    "query": {"type": "string"},
                },
                "required": [],
            },
        ))
        self.register(Tool(
            name="plan_mcp_connectors",
            description="Plan which MCP connectors are relevant for a task without enabling broad access by default.",
            func=lambda task, limit=8: json.dumps(plan_mcp_connectors(task, limit), indent=2),
            parameters={
                "type": "object",
                "properties": {
                    "task": {"type": "string"},
                    "limit": {"type": "integer"},
                },
                "required": ["task"],
            },
        ))

    def _register_graph_tools(self):
        self.register(Tool(
            name="graph_search",
            description="Search the project knowledge graph for nodes matching a query. Use this to find code concepts, files, and modules related to what you're working on. Returns matching nodes with descriptions and file paths.",
            func=graph_search,
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search term to find in the knowledge graph"},
                    "limit": {"type": "integer", "description": "Maximum results (default 20)"},
                },
                "required": ["query"],
            },
        ))

        self.register(Tool(
            name="graph_neighbors",
            description="Explore connections of a node in the knowledge graph. Shows what a file or concept imports, depends on, or is used by. Use this to understand architecture relationships.",
            func=graph_neighbors,
            parameters={
                "type": "object",
                "properties": {
                    "node_id": {"type": "string", "description": "Node ID to explore (e.g., 'file:src/main.ts'). Use graph_search to find node IDs."},
                    "max_neighbors": {"type": "integer", "description": "Maximum neighbors (default 30)"},
                },
                "required": ["node_id"],
            },
        ))

        self.register(Tool(
            name="graph_path",
            description="Find the shortest connection path between two concepts in the knowledge graph. Use this to trace dependencies or understand how two parts of the codebase relate.",
            func=graph_path,
            parameters={
                "type": "object",
                "properties": {
                    "source_query": {"type": "string", "description": "Keyword for the starting concept"},
                    "target_query": {"type": "string", "description": "Keyword for the target concept"},
                },
                "required": ["source_query", "target_query"],
            },
        ))

        self.register(Tool(
            name="graph_explain",
            description="Get a detailed explanation of a specific node in the knowledge graph. Shows metadata, all connections, layer membership, and tour step references.",
            func=graph_explain,
            parameters={
                "type": "object",
                "properties": {
                    "node_id": {"type": "string", "description": "Node ID to explain (e.g., 'file:src/main.ts'). Use graph_search to find node IDs."},
                },
                "required": ["node_id"],
            },
        ))

        self.register(Tool(
            name="graph_stats",
            description="Get statistics and overview of the project knowledge graph. Shows node/edge counts by type, layers, tour steps, and most connected nodes.",
            func=graph_stats,
            parameters={
                "type": "object",
                "properties": {},
                "required": [],
            },
        ))

    def _register_message_tools(self, hub: MessageHub):
        async def _send_message(recipient: str, content: str, thread_id: str = ""):
            msg = hub.send_message("$agent", recipient, content, thread_id=thread_id)
            return json.dumps(msg.to_dict(), indent=2)

        async def _broadcast(content: str):
            msg = hub.broadcast("$agent", content)
            return json.dumps(msg.to_dict(), indent=2)

        async def _get_messages(limit: int = 50, since: float = 0.0):
            msgs = hub.get_messages("$agent", since=since, limit=limit)
            return json.dumps(msgs, indent=2)

        async def _get_thread(thread_id: str):
            msgs = hub.get_thread(thread_id)
            return json.dumps(msgs, indent=2)

        self.register(Tool(
            name="send_message",
            description="Send a direct message to another agent. Use for coordination, asking questions, or sharing findings with a specific agent.",
            func=_send_message,
            parameters={
                "type": "object",
                "properties": {
                    "recipient": {"type": "string", "description": "Name of the recipient agent (e.g., 'coder', 'researcher', 'writer', 'reviewer')"},
                    "content": {"type": "string", "description": "Message content"},
                    "thread_id": {"type": "string", "description": "Optional thread ID to continue an existing conversation"},
                },
                "required": ["recipient", "content"],
            },
        ))

        self.register(Tool(
            name="broadcast_message",
            description="Broadcast a message to ALL agents. Use when you need input from multiple perspectives or want to share something relevant to everyone.",
            func=_broadcast,
            parameters={
                "type": "object",
                "properties": {
                    "content": {"type": "string", "description": "Message to broadcast to all agents"},
                },
                "required": ["content"],
            },
        ))

        self.register(Tool(
            name="get_messages",
            description="Get your recent messages from other agents. Shows who messaged you, what they said, and any active conversations.",
            func=_get_messages,
            parameters={
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "description": "Max messages to return (default 50)"},
                    "since": {"type": "number", "description": "Only messages after this timestamp"},
                },
                "required": [],
            },
        ))

        self.register(Tool(
            name="get_thread",
            description="Get the full history of a conversation thread. Use the thread_id from a previous message to see the full exchange.",
            func=_get_thread,
            parameters={
                "type": "object",
                "properties": {
                    "thread_id": {"type": "string", "description": "Thread ID to retrieve"},
                },
                "required": ["thread_id"],
            },
        ))

    def _register_brainstorm_tools(self, engine: BrainstormEngine):
        async def _initiate_brainstorm(problem: str, context: str = ""):
            session = engine.create_session(problem, context)
            return json.dumps(session.to_dict(), indent=2)

        async def _contribute_idea(session_id: str, perspective: str, idea: str, confidence: float = 0.5):
            bf = engine.add_idea(session_id, "$agent", perspective, idea, confidence)
            if not bf:
                return "Session not found or already closed."
            return json.dumps(bf.to_dict(), indent=2)

        async def _finalize_brainstorm(session_id: str, plan: str, work_packages: list = None):
            ok = engine.finalize(session_id, plan, work_packages)
            if not ok:
                return "Failed to finalize session."
            return json.dumps(engine.get_session(session_id).to_dict(), indent=2)

        async def _get_brainstorm_summary(session_id: str):
            return engine.get_session_summary(session_id)

        self.register(Tool(
            name="initiate_brainstorm",
            description="Start a collaborative brainstorming session for a complex problem. All agents can contribute ideas. Use when the task is complex, multi-step, or needs multiple perspectives.",
            func=_initiate_brainstorm,
            parameters={
                "type": "object",
                "properties": {
                    "problem": {"type": "string", "description": "The problem or challenge to brainstorm"},
                    "context": {"type": "string", "description": "Additional context, constraints, or background information"},
                },
                "required": ["problem"],
            },
        ))

        self.register(Tool(
            name="contribute_idea",
            description="Contribute your perspective and ideas to an active brainstorm session. Share your expertise on what the solution should look like.",
            func=_contribute_idea,
            parameters={
                "type": "object",
                "properties": {
                    "session_id": {"type": "string", "description": "The brainstorm session ID"},
                    "perspective": {"type": "string", "description": "Your perspective or area of expertise"},
                    "idea": {"type": "string", "description": "Your idea or suggestion"},
                    "confidence": {"type": "number", "description": "Confidence in this idea (0.0 to 1.0)"},
                },
                "required": ["session_id", "perspective", "idea"],
            },
        ))

        self.register(Tool(
            name="finalize_brainstorm",
            description="Finalize a brainstorm session with a concrete plan and work packages. Sets the direction for the team.",
            func=_finalize_brainstorm,
            parameters={
                "type": "object",
                "properties": {
                    "session_id": {"type": "string", "description": "The brainstorm session ID"},
                    "plan": {"type": "string", "description": "The agreed-upon plan"},
                    "work_packages": {"type": "array", "items": {"type": "string"}, "description": "List of work packages to assign"},
                },
                "required": ["session_id", "plan"],
            },
        ))

        self.register(Tool(
            name="get_brainstorm_summary",
            description="Get the current status and all ideas from a brainstorm session. Shows what each agent contributed and the current plan.",
            func=_get_brainstorm_summary,
            parameters={
                "type": "object",
                "properties": {
                    "session_id": {"type": "string", "description": "The brainstorm session ID"},
                },
                "required": ["session_id"],
            },
        ))

    def _register_debug_tools(self, debug: DebugCollaboration):
        async def _request_help(description: str, suspected_area: str = "", attempted_fixes: list = None):
            issue = debug.report_issue("$agent", description, suspected_area, attempted_fixes)
            return json.dumps(issue.to_dict(), indent=2)

        async def _propose_fix(issue_id: str, description: str, code: str = ""):
            proposal = debug.propose_fix(issue_id, "$agent", description, code)
            if not proposal:
                return "Issue not found or already resolved."
            return json.dumps(proposal.to_dict(), indent=2)

        async def _review_fix(proposal_id: str, decision: str, feedback: str = ""):
            review = debug.review_fix(proposal_id, "$agent", decision, feedback)
            if not review:
                return "Proposal not found."
            return json.dumps(review.to_dict(), indent=2)

        async def _apply_fix(proposal_id: str):
            ok = debug.apply_fix(proposal_id, "$agent")
            if not ok:
                return "Fix not approved or already applied."
            return f"Fix {proposal_id} applied successfully."

        async def _get_issue_status(issue_id: str):
            return debug.get_issue_summary(issue_id)

        self.register(Tool(
            name="request_help",
            description="Request help from other agents for a bug or problem you're stuck on. Other agents will see the issue and can propose fixes.",
            func=_request_help,
            parameters={
                "type": "object",
                "properties": {
                    "description": {"type": "string", "description": "Clear description of the issue"},
                    "suspected_area": {"type": "string", "description": "Area you suspect the issue is in (e.g., 'database', 'UI', 'API')"},
                    "attempted_fixes": {"type": "array", "items": {"type": "string"}, "description": "What you've already tried"},
                },
                "required": ["description"],
            },
        ))

        self.register(Tool(
            name="propose_fix",
            description="Propose a solution to another agent's problem. Include your analysis and the fix itself. Other agents can review your proposal.",
            func=_propose_fix,
            parameters={
                "type": "object",
                "properties": {
                    "issue_id": {"type": "string", "description": "The issue ID from a help request"},
                    "description": {"type": "string", "description": "Explanation of your proposed fix"},
                    "code": {"type": "string", "description": "The actual fix code (optional)"},
                },
                "required": ["issue_id", "description"],
            },
        ))

        self.register(Tool(
            name="review_fix",
            description="Review another agent's proposed fix. Approve if it looks good, reject with feedback if it needs changes, or request revisions.",
            func=_review_fix,
            parameters={
                "type": "object",
                "properties": {
                    "proposal_id": {"type": "string", "description": "The fix proposal ID to review"},
                    "decision": {"type": "string", "enum": ["approve", "reject", "revise"], "description": "Your decision"},
                    "feedback": {"type": "string", "description": "Constructive feedback explaining your decision"},
                },
                "required": ["proposal_id", "decision"],
            },
        ))

        self.register(Tool(
            name="apply_fix",
            description="Apply an approved fix. Only call this after a fix has been reviewed and approved.",
            func=_apply_fix,
            parameters={
                "type": "object",
                "properties": {
                    "proposal_id": {"type": "string", "description": "The approved fix proposal ID"},
                },
                "required": ["proposal_id"],
            },
        ))

        self.register(Tool(
            name="get_issue_status",
            description="Check the full status of a debugging issue — see all proposals, reviews, and current state.",
            func=_get_issue_status,
            parameters={
                "type": "object",
                "properties": {
                    "issue_id": {"type": "string", "description": "The issue ID"},
                },
                "required": ["issue_id"],
            },
        ))

    def _register_lesson_tools(self, learner: LessonLearner):
        async def _log_lesson(context: str, outcome: str, lesson: str, tags: list = None, success: bool = True):
            lsn = learner.log_lesson("$agent", context, outcome, lesson, tags, success)
            return json.dumps(lsn.to_dict(), indent=2)

        async def _get_relevant_lessons(context: str, max_results: int = 5):
            lessons = learner.get_lessons_for_prompt("$agent", context, max_results)
            if not lessons:
                return "No relevant lessons found."
            return lessons

        async def _get_learning_stats():
            return json.dumps(learner.get_stats(), indent=2)

        self.register(Tool(
            name="log_lesson",
            description="Log a lesson learned from your work. This makes the swarm smarter over time — future agents facing similar tasks will benefit from your experience.",
            func=_log_lesson,
            parameters={
                "type": "object",
                "properties": {
                    "context": {"type": "string", "description": "What you were working on"},
                    "outcome": {"type": "string", "description": "What happened (success or failure)"},
                    "lesson": {"type": "string", "description": "What you learned — the key insight"},
                    "tags": {"type": "array", "items": {"type": "string"}, "description": "Keywords for matching this lesson to future tasks"},
                    "success": {"type": "boolean", "description": "Whether the outcome was successful"},
                },
                "required": ["context", "outcome", "lesson"],
            },
        ))

        self.register(Tool(
            name="get_relevant_lessons",
            description="Retrieve lessons learned from previous swarm runs that are relevant to your current task. Use this when starting a task to avoid past mistakes and apply proven patterns.",
            func=_get_relevant_lessons,
            parameters={
                "type": "object",
                "properties": {
                    "context": {"type": "string", "description": "Describe what you're working on to find relevant lessons"},
                    "max_results": {"type": "integer", "description": "Max lessons to return (default 5)"},
                },
                "required": ["context"],
            },
        ))

        self.register(Tool(
            name="get_learning_stats",
            description="Get statistics on what the swarm has learned — total lessons, per-agent breakdown, and success rates.",
            func=_get_learning_stats,
            parameters={
                "type": "object",
                "properties": {},
                "required": [],
            },
        ))

    def inject_sub_agent_tools(self, sub_agent_manager_ref):
        """Inject spawn_agent tool that references the sub-agent manager."""

        async def _spawn_agent(agent_name: str, task: str):
            mgr = sub_agent_manager_ref()
            if mgr is None:
                return "Sub-agent manager not available"
            result = await mgr.spawn(agent_name, task, SharedState(user_input=task), verbose=False)
            return json.dumps(result.to_dict(), indent=2)

        self.register(Tool(
            name="spawn_agent",
            description="Delegate a task to another agent. The sub-agent runs independently and returns its result. Use for parallel work or specialized tasks.",
            func=_spawn_agent,
            parameters={
                "type": "object",
                "properties": {
                    "agent_name": {"type": "string", "description": "Name of the agent to delegate to (e.g., 'researcher', 'coder', 'writer')"},
                    "task": {"type": "string", "description": "Detailed task description for the sub-agent"},
                },
                "required": ["agent_name", "task"],
            },
        ))

    def _register_finance_tools(self):
        for defn in FINANCE_TOOL_DEFINITIONS:
            self.register(Tool(
                name=defn["name"],
                description=defn["description"],
                func=defn["func"],
                parameters=defn["parameters"],
            ))

    def _register_shared_memory_tools(self):
        for defn in SHARED_MEMORY_TOOL_DEFINITIONS:
            self.register(Tool(
                name=defn["name"],
                description=defn["description"],
                func=defn["func"],
                parameters=defn["parameters"],
            ))

    def _register_system_awareness_tools(self):
        for defn in SYSTEM_AWARENESS_TOOL_DEFINITIONS:
            self.register(Tool(
                name=defn["name"],
                description=defn["description"],
                func=defn["func"],
                parameters=defn["parameters"],
            ))
