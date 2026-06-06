from __future__ import annotations

from dataclasses import dataclass

from swarm.core.agent import Agent


PILLARS = ("code", "see", "design", "act")


@dataclass(frozen=True)
class AgentSpec:
    name: str
    title: str
    pillar: str
    category: str
    description: str
    capabilities: tuple[str, ...]
    tools: tuple[str, ...] = ()
    temperature: float = 0.25
    task_type: str = "general"
    model_preference: str = "auto"
    sub_agent_roles: tuple[str, ...] = ()


COMMON_COLLAB_TOOLS = (
    "send_message",
    "broadcast_message",
    "get_messages",
    "get_thread",
    "initiate_brainstorm",
    "contribute_idea",
    "get_brainstorm_summary",
    "log_lesson",
    "get_relevant_lessons",
    "spawn_agent",
    "plan_temporary_vision",
)

WEB_JOB_TOOLS = (
    "plan_web_scraper",
    "plan_job_finder_applier",
)

APP_BUILD_TOOLS = (
    "plan_app_builder",
    "plan_app_tester",
    "plan_backend_maker",
)

HERMES_EVOLUTION_TOOLS = (
    "plan_hermes_evolution",
    "propose_hermes_skill",
    "validate_hermes_skill",
    "persist_hermes_skill",
    "list_hermes_skills",
)

DESIGN_3D_TOOLS = (
    "plan_3d_design_model",
    "classify_3d_design_request",
    "plan_building_design",
)

ANIMATION_TOOLS = (
    "plan_animation",
    "plan_mockup_video",
)

CODE_TOOLS = (
    "read_file",
    "write_file",
    "list_directory",
    "run_python",
    "run_react_doctor",
    "compact_context",
    "plan_docs_integration",
)

REVIEW_TOOLS = (
    "preflight_review_agent_work",
    "format_pr_inline_comments",
    "run_react_doctor",
    "read_file",
    "list_directory",
)

RESEARCH_TOOLS = ("search_web", "read_file", "list_directory")
DOC_TOOLS = ("read_file", "write_file", "list_directory", "plan_docs_integration", "compact_context")
BROWSER_TOOLS = (
    "browser_open",
    "browser_snapshot",
    "browser_click",
    "browser_get_title",
    "browser_stop",
)

DEFAULT_MODEL_PREFERENCES = {
    "coding": "coding",
    "core": "reasoning",
    "business": "reasoning",
    "creative": "chat",
}

AGENT_MODEL_PREFERENCES = {
    "triage": "best",
    "coder": "coding",
    "backend_api": "coding",
    "frontend_ui": "coding",
    "app_builder": "coding",
    "backend_maker": "coding",
    "app_tester": "coding",
    "web_scraper": "coding",
    "job_finder": "reasoning",
    "building_designer": "vision",
    "animator": "video_generation",
    "reviewer": "coding",
    "ai_reviewer": "coding",
    "security": "reasoning",
    "testing": "coding",
    "debugging": "coding",
    "photo_editor": "image_generation",
    "video_editor": "video_generation",
    "voice_transcriber": "speech_to_text",
    "voice_generator": "text_to_speech",
    "figma_controller": "vision",
    "hermes": "reasoning",
    "text_editor": "chat",
    "prompt_generator": "chat",
    "documentation": "chat",
    "council_master": "reasoning",
}

AGENT_SUB_AGENT_ROLES = {
    "triage": ("researcher", "product_manager", "council_master"),
    "coder": ("backend_api", "frontend_ui", "testing", "security"),
    "backend_api": ("backend_maker", "security", "testing", "documentation"),
    "frontend_ui": ("app_tester", "ux_research", "testing", "documentation"),
    "app_builder": ("frontend_ui", "backend_maker", "app_tester", "security"),
    "backend_maker": ("security", "testing", "documentation"),
    "app_tester": ("debugging", "security", "frontend_ui", "backend_maker"),
    "web_scraper": ("researcher", "analytics", "security"),
    "job_finder": ("web_scraper", "writer", "legal"),
    "building_designer": ("design", "animator", "figma_controller", "ux_research"),
    "reviewer": ("ai_reviewer", "testing", "security", "coder"),
    "ai_reviewer": ("security", "testing", "debugging", "coder"),
    "security": ("testing", "debugging", "legal"),
    "testing": ("debugging", "coder", "reviewer"),
    "debugging": ("testing", "coder", "security"),
    "marketing": ("analytics", "sales", "ux_research"),
    "finance": ("analytics", "legal", "trading"),
    "analytics": ("researcher", "finance", "marketing"),
    "trading": ("finance", "analytics", "legal"),
    "legal": ("security", "finance", "product_manager"),
    "ux_research": ("analytics", "design", "localization"),
    "localization": ("ux_research", "writer", "design"),
    "product_manager": ("analytics", "ux_research", "finance", "coder"),
    "sales": ("marketing", "analytics", "product_manager"),
    "design": ("building_designer", "animator", "ux_research", "figma_controller", "writer", "prompt_generator"),
    "photo_editor": ("design", "ux_research", "figma_controller"),
    "video_editor": ("animator", "design", "writer", "marketing", "prompt_generator"),
    "animator": ("video_editor", "design", "prompt_generator", "figma_controller"),
    "hermes": ("researcher", "coder", "testing", "documentation"),
    "voice_transcriber": ("writer", "localization", "analytics"),
    "voice_generator": ("writer", "localization", "video_editor"),
    "figma_controller": ("design", "ux_research", "coder"),
    "writer": ("text_editor", "marketing", "localization", "reviewer"),
    "documentation": ("writer", "reviewer", "localization"),
    "text_editor": ("writer", "localization", "reviewer"),
    "prompt_generator": ("writer", "photo_editor", "video_editor", "design"),
    "researcher": ("analytics", "legal", "ux_research"),
    "council_master": ("researcher", "security", "testing", "analytics", "legal", "product_manager"),
}


AGENT_SPECS: tuple[AgentSpec, ...] = (
    AgentSpec("triage", "Triage Agent", "act", "core", "Routes work to the best specialist.", ("classify requests", "split tasks", "handoff"), COMMON_COLLAB_TOOLS, 0.2),
    AgentSpec("hermes", "Hermes Self-Evolution Agent", "act", "core", "Observes repeated work patterns, creates reusable skills, validates them, versions them, and feeds approved skills back into future swarm runs.", ("self evolution", "skill creation", "skill validation", "versioned memory", "reuse planning"), HERMES_EVOLUTION_TOOLS + COMMON_COLLAB_TOOLS, 0.18, "reasoning"),
    AgentSpec("researcher", "Research Agent", "see", "core", "Researches facts, sources, markets, and prior art.", ("source discovery", "evidence synthesis", "conflict checks", "browser inspection"), RESEARCH_TOOLS + BROWSER_TOOLS + COMMON_COLLAB_TOOLS, 0.3, "reasoning"),
    AgentSpec("web_scraper", "Web Scraper Agent", "see", "coding", "Plans and runs compliant web scraping with browser/API fallback, source tracking, extraction validation, and rate-limit guardrails.", ("web scraping", "browser extraction", "structured data", "source tracking", "rate-limit planning"), WEB_JOB_TOOLS + BROWSER_TOOLS + RESEARCH_TOOLS + COMMON_COLLAB_TOOLS, 0.18, "coding"),
    AgentSpec("coder", "Coding Agent", "code", "coding", "Builds features, refactors code, and writes implementation notes.", ("implementation", "refactoring", "integration"), CODE_TOOLS + COMMON_COLLAB_TOOLS, 0.2, "coding"),
    AgentSpec("backend_api", "Backend API Agent", "code", "coding", "Builds backend routes, data contracts, service logic, validation, auth boundaries, and API integration tests.", ("api routes", "service logic", "database contracts", "auth boundaries", "backend tests"), CODE_TOOLS + COMMON_COLLAB_TOOLS, 0.18, "coding"),
    AgentSpec("frontend_ui", "Frontend UI Agent", "design", "coding", "Builds frontend UI, state, accessibility, responsive layout, component wiring, and browser-facing flows.", ("components", "state", "accessibility", "responsive UI", "frontend tests"), CODE_TOOLS + BROWSER_TOOLS + COMMON_COLLAB_TOOLS, 0.22, "coding"),
    AgentSpec("app_builder", "App Builder Agent", "code", "coding", "Builds full apps by coordinating frontend, backend, tests, docs, and integration review.", ("requirements", "full app build", "frontend/backend wiring", "release evidence"), APP_BUILD_TOOLS + CODE_TOOLS + COMMON_COLLAB_TOOLS, 0.2, "coding"),
    AgentSpec("backend_maker", "Backend Maker Agent", "code", "coding", "Creates backend APIs, schemas, auth boundaries, validation, permissions, tests, and docs.", ("API contracts", "schemas", "auth", "validation", "backend tests"), APP_BUILD_TOOLS + CODE_TOOLS + COMMON_COLLAB_TOOLS, 0.16, "coding"),
    AgentSpec("app_tester", "App Tester Agent", "code", "coding", "Tests apps across unit, integration, browser, accessibility, responsive, performance, and security-smoke checks.", ("QA plans", "browser tests", "accessibility", "performance", "bug reports"), APP_BUILD_TOOLS + CODE_TOOLS + BROWSER_TOOLS + COMMON_COLLAB_TOOLS, 0.13, "coding"),
    AgentSpec("reviewer", "Reviewer Agent", "code", "coding", "Reviews quality, correctness, and release readiness.", ("code review", "risk review", "acceptance checks"), CODE_TOOLS + COMMON_COLLAB_TOOLS, 0.15, "coding"),
    AgentSpec("ai_reviewer", "AI Reviewer Agent", "code", "coding", "Reviews every individual agent output before integration, posts PR inline comment payloads, and sends fixes back to the responsible agent.", ("security vulnerability review", "performance review", "logic error review", "PR inline comments", "pre-integration debugging"), REVIEW_TOOLS + COMMON_COLLAB_TOOLS, 0.1, "coding"),
    AgentSpec("writer", "Writer Agent", "design", "creative", "Creates user-facing copy, docs, and summaries.", ("documentation", "release notes", "narrative"), COMMON_COLLAB_TOOLS, 0.35, "chat"),
    AgentSpec("documentation", "Documentation Agent", "design", "creative", "Writes README updates, install guides, API docs, changelogs, and docs-source-backed implementation notes.", ("readme", "install guide", "api docs", "changelog", "docs integration"), DOC_TOOLS + COMMON_COLLAB_TOOLS, 0.25, "chat"),
    AgentSpec("text_editor", "Text Editor Agent", "design", "creative", "Edits, rewrites, proofreads, and adapts text while preserving intent.", ("line editing", "tone rewrite", "proofreading", "summarization"), COMMON_COLLAB_TOOLS, 0.25, "chat"),
    AgentSpec("prompt_generator", "Prompt Generation Agent", "design", "creative", "Creates concise, reusable prompts for text, voice, image, video, design, browser, and coding agents.", ("prompt design", "negative prompts", "voice prompts", "style prompts", "test prompts"), COMMON_COLLAB_TOOLS, 0.3, "chat"),
    AgentSpec("security", "Security Agent", "code", "coding", "Threat models, audits auth/data flows, and checks abuse paths.", ("threat modeling", "vulnerability checks", "secret handling"), CODE_TOOLS + COMMON_COLLAB_TOOLS, 0.1, "coding"),
    AgentSpec("testing", "Testing Agent", "code", "coding", "Designs and runs aggressive test coverage across edge cases.", ("unit tests", "integration tests", "browser tests", "regression checks"), CODE_TOOLS + BROWSER_TOOLS + COMMON_COLLAB_TOOLS, 0.15, "coding"),
    AgentSpec("debugging", "Debugging Agent", "code", "coding", "Finds root causes and proposes minimal fixes.", ("trace analysis", "failure reproduction", "fix validation"), CODE_TOOLS + COMMON_COLLAB_TOOLS, 0.15, "coding"),
    AgentSpec("marketing", "Marketing Agent", "act", "business", "Assesses positioning, launch demand, and growth impact.", ("market demand", "messaging", "campaign strategy"), RESEARCH_TOOLS + COMMON_COLLAB_TOOLS, 0.35, "chat"),
    AgentSpec("job_finder", "Job Finder & Applier Agent", "act", "business", "Finds jobs, scores fit, drafts tailored applications, and applies only after explicit user approval.", ("job search", "fit scoring", "resume tailoring", "application drafts", "approval-gated apply"), WEB_JOB_TOOLS + BROWSER_TOOLS + RESEARCH_TOOLS + COMMON_COLLAB_TOOLS, 0.25, "reasoning"),
    AgentSpec("finance", "Finance Agent", "act", "business", "Models costs, ROI, pricing, and financial risk.", ("ROI analysis", "cost modeling", "budget impact"), RESEARCH_TOOLS + COMMON_COLLAB_TOOLS, 0.2, "reasoning"),
    AgentSpec("analytics", "Analytics Agent", "see", "business", "Defines metrics, instrumentation, and data-backed conclusions.", ("metric design", "trend analysis", "data quality"), RESEARCH_TOOLS + BROWSER_TOOLS + COMMON_COLLAB_TOOLS, 0.2, "reasoning"),
    AgentSpec("trading", "Trading Agent", "act", "business", "Analyzes market structure and produces risk-scored trade plans.", ("trend analysis", "risk management", "execution plans"), RESEARCH_TOOLS + COMMON_COLLAB_TOOLS, 0.15, "reasoning"),
    AgentSpec("legal", "Legal Agent", "act", "business", "Flags compliance, contract, licensing, and policy risk.", ("compliance review", "policy risk", "licensing"), RESEARCH_TOOLS + COMMON_COLLAB_TOOLS, 0.1, "reasoning"),
    AgentSpec("ux_research", "UX Research Agent", "see", "business", "Studies user needs, usability, adoption, and feedback signals.", ("user interviews", "journey analysis", "browser usability checks", "usability risk"), RESEARCH_TOOLS + BROWSER_TOOLS + COMMON_COLLAB_TOOLS, 0.3, "reasoning"),
    AgentSpec("localization", "Localization Agent", "design", "business", "Adapts product language, formatting, and culture-specific UX.", ("translation QA", "locale formats", "cultural fit"), COMMON_COLLAB_TOOLS, 0.25, "chat"),
    AgentSpec("product_manager", "Product Management Agent", "act", "business", "Turns goals into roadmap, requirements, and acceptance criteria.", ("prioritization", "requirements", "tradeoff calls"), COMMON_COLLAB_TOOLS, 0.25, "reasoning"),
    AgentSpec("sales", "Sales Agent", "act", "business", "Evaluates buyer fit, objections, and revenue paths.", ("ICP fit", "objection handling", "pipeline impact"), RESEARCH_TOOLS + COMMON_COLLAB_TOOLS, 0.35, "chat"),
    AgentSpec("building_designer", "Building Interior & Exterior Designer", "design", "creative", "Designs building interiors and exteriors with layout, facade, materials, lighting, circulation, and 3D handoff planning.", ("interior design", "exterior design", "floor plans", "facade direction", "3D building mockups"), DESIGN_3D_TOOLS + BROWSER_TOOLS + COMMON_COLLAB_TOOLS, 0.28, "vision"),
    AgentSpec("design", "Design Agent", "design", "creative", "Creates product design direction, flows, layout, interaction patterns, and faithful 3D plans for user-owned designs.", ("UI flows", "visual systems", "interaction design", "user-owned 3D design modeling"), DESIGN_3D_TOOLS + COMMON_COLLAB_TOOLS, 0.35, "chat"),
    AgentSpec("photo_editor", "Image Generation & Edit Agent", "see", "creative", "Plans, generates, and critiques image assets, crops, retouching, masking, restoration, and asset polish.", ("image generation", "image critique", "retouch plans", "masking guidance", "asset QA"), DESIGN_3D_TOOLS + COMMON_COLLAB_TOOLS, 0.3, "image_generation"),
    AgentSpec("video_editor", "Video Generation & Edit Agent", "see", "creative", "Plans, generates, and critiques video clips, cuts, pacing, captions, transitions, color, thumbnails, and video polish.", ("video generation", "story pacing", "caption review", "timeline QA", "motion notes"), ANIMATION_TOOLS + DESIGN_3D_TOOLS + COMMON_COLLAB_TOOLS, 0.3, "video_generation"),
    AgentSpec("animator", "Animator Agent", "design", "creative", "Plans and reviews 2D, 3D, UI, logo, product, character, mockup, and video animations with storyboard, timing, keyframes, preview render, and export QA.", ("storyboards", "keyframes", "motion arcs", "camera moves", "animation QA"), ANIMATION_TOOLS + DESIGN_3D_TOOLS + COMMON_COLLAB_TOOLS, 0.28, "video_generation"),
    AgentSpec("voice_transcriber", "Voice-to-Text Agent", "see", "creative", "Plans and runs speech-to-text transcription, diarization handoff, subtitle drafts, and transcript cleanup.", ("speech to text", "audio transcription", "subtitle draft", "speaker note cleanup"), COMMON_COLLAB_TOOLS, 0.2, "speech_to_text"),
    AgentSpec("voice_generator", "Voice Generation Agent", "design", "creative", "Plans and runs text-to-speech voiceovers, narration drafts, voice style prompts, and audio export QA.", ("text to speech", "voiceover generation", "narration", "audio export QA"), COMMON_COLLAB_TOOLS, 0.25, "text_to_speech"),
    AgentSpec("figma_controller", "Figma Control Agent", "design", "creative", "Coordinates Figma-oriented layout, component, and handoff changes.", ("component control", "design QA", "handoff specs", "browser prototype checks"), BROWSER_TOOLS + COMMON_COLLAB_TOOLS, 0.25, "vision"),
    AgentSpec("council_master", "Council Master", "act", "core", "Runs evidence review, debate, voting, and final confidence scoring.", ("debate moderation", "vote tallying", "confidence scoring"), COMMON_COLLAB_TOOLS, 0.1, "reasoning"),
)


def build_agent_from_spec(spec: AgentSpec, handoff_targets: list[str] | None = None) -> Agent:
    if spec.pillar not in PILLARS:
        raise ValueError(f"Unknown pillar for {spec.name}: {spec.pillar}")
    capabilities = "\n".join(f"- {item}" for item in spec.capabilities)
    model_preference = (
        spec.model_preference
        if spec.model_preference != "auto"
        else AGENT_MODEL_PREFERENCES.get(
            spec.name,
            DEFAULT_MODEL_PREFERENCES.get(spec.category, spec.task_type),
        )
    )
    sub_agent_roles = spec.sub_agent_roles or AGENT_SUB_AGENT_ROLES.get(spec.name, ())
    prompt = (
        f"You are the **{spec.title}** in Agent Swarm.\n\n"
        f"Pillar: {spec.pillar}\nCategory: {spec.category}\n\n"
        f"Preferred model type: {model_preference}\n"
        f"Default sub-agents: {', '.join(sub_agent_roles) if sub_agent_roles else 'none'}\n\n"
        f"Mission: {spec.description}\n\n"
        f"Capabilities:\n{capabilities}\n\n"
        "When participating in council review, provide evidence, risks, edge cases, "
        "a clear proceed/reject recommendation, and a confidence score."
    )
    return Agent(
        name=spec.name,
        system_prompt=prompt,
        description=spec.description,
        tools=list(spec.tools),
        handoff_targets=handoff_targets or [],
        temperature=spec.temperature,
        task_type=spec.task_type,
        pillar=spec.pillar,
        category=spec.category,
        model_preference=model_preference,
        sub_agent_roles=list(sub_agent_roles),
    )


def create_specialist_agents(mesh: bool = True) -> list[Agent]:
    names = [spec.name for spec in AGENT_SPECS]
    agents = []
    for spec in AGENT_SPECS:
        targets = [name for name in names if name != spec.name] if mesh else []
        agents.append(build_agent_from_spec(spec, targets))
    return agents


def get_agent_spec(name: str) -> AgentSpec | None:
    return next((spec for spec in AGENT_SPECS if spec.name == name), None)


def summarize_catalog() -> dict[str, list[str]]:
    summary: dict[str, list[str]] = {pillar: [] for pillar in PILLARS}
    for spec in AGENT_SPECS:
        summary[spec.pillar].append(spec.name)
    return summary
