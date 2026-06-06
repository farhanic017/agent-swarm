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
)

CODE_TOOLS = (
    "read_file",
    "write_file",
    "list_directory",
    "run_python",
    "run_react_doctor",
)

REVIEW_TOOLS = (
    "preflight_review_agent_work",
    "format_pr_inline_comments",
    "run_react_doctor",
    "read_file",
    "list_directory",
)

RESEARCH_TOOLS = ("search_web", "read_file", "list_directory")
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
    "reviewer": "coding",
    "ai_reviewer": "coding",
    "security": "reasoning",
    "testing": "coding",
    "debugging": "coding",
    "photo_editor": "image_generation",
    "video_editor": "video_generation",
    "figma_controller": "vision",
    "text_editor": "chat",
    "prompt_generator": "chat",
    "council_master": "reasoning",
}

AGENT_SUB_AGENT_ROLES = {
    "triage": ("researcher", "product_manager", "council_master"),
    "coder": ("testing", "security", "reviewer", "debugging"),
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
    "design": ("ux_research", "figma_controller", "writer", "prompt_generator"),
    "photo_editor": ("design", "ux_research", "figma_controller"),
    "video_editor": ("design", "writer", "marketing", "prompt_generator"),
    "figma_controller": ("design", "ux_research", "coder"),
    "writer": ("text_editor", "marketing", "localization", "reviewer"),
    "text_editor": ("writer", "localization", "reviewer"),
    "prompt_generator": ("writer", "photo_editor", "video_editor", "design"),
    "researcher": ("analytics", "legal", "ux_research"),
    "council_master": ("researcher", "security", "testing", "analytics", "legal", "product_manager"),
}


AGENT_SPECS: tuple[AgentSpec, ...] = (
    AgentSpec("triage", "Triage Agent", "act", "core", "Routes work to the best specialist.", ("classify requests", "split tasks", "handoff"), COMMON_COLLAB_TOOLS, 0.2),
    AgentSpec("researcher", "Research Agent", "see", "core", "Researches facts, sources, markets, and prior art.", ("source discovery", "evidence synthesis", "conflict checks", "browser inspection"), RESEARCH_TOOLS + BROWSER_TOOLS + COMMON_COLLAB_TOOLS, 0.3, "reasoning"),
    AgentSpec("coder", "Coding Agent", "code", "coding", "Builds features, refactors code, and writes implementation notes.", ("implementation", "refactoring", "integration"), CODE_TOOLS + COMMON_COLLAB_TOOLS, 0.2, "coding"),
    AgentSpec("reviewer", "Reviewer Agent", "code", "coding", "Reviews quality, correctness, and release readiness.", ("code review", "risk review", "acceptance checks"), CODE_TOOLS + COMMON_COLLAB_TOOLS, 0.15, "coding"),
    AgentSpec("ai_reviewer", "AI Reviewer Agent", "code", "coding", "Reviews every individual agent output before integration, posts PR inline comment payloads, and sends fixes back to the responsible agent.", ("security vulnerability review", "performance review", "logic error review", "PR inline comments", "pre-integration debugging"), REVIEW_TOOLS + COMMON_COLLAB_TOOLS, 0.1, "coding"),
    AgentSpec("writer", "Writer Agent", "design", "creative", "Creates user-facing copy, docs, and summaries.", ("documentation", "release notes", "narrative"), COMMON_COLLAB_TOOLS, 0.35, "chat"),
    AgentSpec("text_editor", "Text Editor Agent", "design", "creative", "Edits, rewrites, proofreads, and adapts text while preserving intent.", ("line editing", "tone rewrite", "proofreading", "summarization"), COMMON_COLLAB_TOOLS, 0.25, "chat"),
    AgentSpec("prompt_generator", "Prompt Generation Agent", "design", "creative", "Creates concise, reusable prompts for text, image, video, design, browser, and coding agents.", ("prompt design", "negative prompts", "style prompts", "test prompts"), COMMON_COLLAB_TOOLS, 0.3, "chat"),
    AgentSpec("security", "Security Agent", "code", "coding", "Threat models, audits auth/data flows, and checks abuse paths.", ("threat modeling", "vulnerability checks", "secret handling"), CODE_TOOLS + COMMON_COLLAB_TOOLS, 0.1, "coding"),
    AgentSpec("testing", "Testing Agent", "code", "coding", "Designs and runs aggressive test coverage across edge cases.", ("unit tests", "integration tests", "browser tests", "regression checks"), CODE_TOOLS + BROWSER_TOOLS + COMMON_COLLAB_TOOLS, 0.15, "coding"),
    AgentSpec("debugging", "Debugging Agent", "code", "coding", "Finds root causes and proposes minimal fixes.", ("trace analysis", "failure reproduction", "fix validation"), CODE_TOOLS + COMMON_COLLAB_TOOLS, 0.15, "coding"),
    AgentSpec("marketing", "Marketing Agent", "act", "business", "Assesses positioning, launch demand, and growth impact.", ("market demand", "messaging", "campaign strategy"), RESEARCH_TOOLS + COMMON_COLLAB_TOOLS, 0.35, "chat"),
    AgentSpec("finance", "Finance Agent", "act", "business", "Models costs, ROI, pricing, and financial risk.", ("ROI analysis", "cost modeling", "budget impact"), RESEARCH_TOOLS + COMMON_COLLAB_TOOLS, 0.2, "reasoning"),
    AgentSpec("analytics", "Analytics Agent", "see", "business", "Defines metrics, instrumentation, and data-backed conclusions.", ("metric design", "trend analysis", "data quality"), RESEARCH_TOOLS + BROWSER_TOOLS + COMMON_COLLAB_TOOLS, 0.2, "reasoning"),
    AgentSpec("trading", "Trading Agent", "act", "business", "Analyzes market structure and produces risk-scored trade plans.", ("trend analysis", "risk management", "execution plans"), RESEARCH_TOOLS + COMMON_COLLAB_TOOLS, 0.15, "reasoning"),
    AgentSpec("legal", "Legal Agent", "act", "business", "Flags compliance, contract, licensing, and policy risk.", ("compliance review", "policy risk", "licensing"), RESEARCH_TOOLS + COMMON_COLLAB_TOOLS, 0.1, "reasoning"),
    AgentSpec("ux_research", "UX Research Agent", "see", "business", "Studies user needs, usability, adoption, and feedback signals.", ("user interviews", "journey analysis", "browser usability checks", "usability risk"), RESEARCH_TOOLS + BROWSER_TOOLS + COMMON_COLLAB_TOOLS, 0.3, "reasoning"),
    AgentSpec("localization", "Localization Agent", "design", "business", "Adapts product language, formatting, and culture-specific UX.", ("translation QA", "locale formats", "cultural fit"), COMMON_COLLAB_TOOLS, 0.25, "chat"),
    AgentSpec("product_manager", "Product Management Agent", "act", "business", "Turns goals into roadmap, requirements, and acceptance criteria.", ("prioritization", "requirements", "tradeoff calls"), COMMON_COLLAB_TOOLS, 0.25, "reasoning"),
    AgentSpec("sales", "Sales Agent", "act", "business", "Evaluates buyer fit, objections, and revenue paths.", ("ICP fit", "objection handling", "pipeline impact"), RESEARCH_TOOLS + COMMON_COLLAB_TOOLS, 0.35, "chat"),
    AgentSpec("design", "Design Agent", "design", "creative", "Creates product design direction, flows, layout, and interaction patterns.", ("UI flows", "visual systems", "interaction design"), COMMON_COLLAB_TOOLS, 0.35, "chat"),
    AgentSpec("photo_editor", "Image Generation & Edit Agent", "see", "creative", "Plans, generates, and critiques image assets, crops, retouching, masking, restoration, and asset polish.", ("image generation", "image critique", "retouch plans", "masking guidance", "asset QA"), COMMON_COLLAB_TOOLS, 0.3, "image_generation"),
    AgentSpec("video_editor", "Video Generation & Edit Agent", "see", "creative", "Plans, generates, and critiques video clips, cuts, pacing, captions, transitions, color, thumbnails, and video polish.", ("video generation", "story pacing", "caption review", "timeline QA", "motion notes"), COMMON_COLLAB_TOOLS, 0.3, "video_generation"),
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
