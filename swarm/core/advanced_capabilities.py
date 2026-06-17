from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AdvancedCapability:
    key: str
    category: str
    title: str
    purpose: str
    outputs: tuple[str, ...]
    guardrails: tuple[str, ...]
    suggested_agents: tuple[str, ...]
    triggers: tuple[str, ...]

    def to_dict(self) -> dict:
        return {
            "key": self.key,
            "category": self.category,
            "title": self.title,
            "purpose": self.purpose,
            "outputs": list(self.outputs),
            "guardrails": list(self.guardrails),
            "suggested_agents": list(self.suggested_agents),
            "triggers": list(self.triggers),
        }


DEFAULT_GUARDRAILS = (
    "run council review before execution",
    "keep file and API access scoped to the project",
    "show planned changes before destructive actions",
    "capture tests, costs, and handoff notes as artifacts",
)


CAPABILITIES: tuple[AdvancedCapability, ...] = (
    AdvancedCapability("checkpoint_resume", "core_orchestration", "Checkpoint / Resume", "Persist run checkpoints and resume from the last completed agent after crashes or interruption.", ("checkpoint manifest", "resume cursor", "completed-agent map"), DEFAULT_GUARDRAILS, ("checkpoint_manager", "triage", "council_master"), ("checkpoint", "resume", "crash")),
    AdvancedCapability("swarm_replay", "core_orchestration", "Swarm Replay", "Record deterministic run inputs, decisions, tool calls, and outputs so a run can be replayed for debugging.", ("replay log", "deterministic seed", "replay report"), DEFAULT_GUARDRAILS, ("replay_runner", "testing", "debugging"), ("replay", "deterministic")),
    AdvancedCapability("cost_estimator", "core_orchestration", "Cost Estimator", "Estimate token and provider cost before starting a swarm run.", ("token projection", "cost projection", "budget warning"), DEFAULT_GUARDRAILS, ("cost_optimizer", "cost_dashboard", "triage"), ("cost", "tokens", "budget")),
    AdvancedCapability("parallel_execution", "core_orchestration", "Parallel Agent Execution", "Plan which agents can run concurrently and which must wait on dependencies.", ("parallel groups", "dependency map", "merge gate"), DEFAULT_GUARDRAILS, ("priority_scheduler", "pipeline_manager", "council_master"), ("parallel", "simultaneous", "dependency")),
    AdvancedCapability("priority_queue", "core_orchestration", "Priority Queue", "Let urgent tasks jump ahead while preserving fairness and auditability.", ("priority score", "queue order", "escalation reason"), DEFAULT_GUARDRAILS, ("priority_scheduler", "triage", "product_manager"), ("priority", "urgent", "queue")),
    AdvancedCapability("agent_retry_backoff", "core_orchestration", "Agent Retry With Exponential Backoff", "Retry failed agents with exponential backoff, cooldown detection, and replacement-model memory handoff.", ("retry schedule", "failure class", "handoff summary"), DEFAULT_GUARDRAILS, ("debugging", "provider_health_monitor", "triage"), ("retry", "backoff", "rate limit")),
    AdvancedCapability("conditional_branching", "core_orchestration", "Conditional Branching", "Route next agents based on structured outputs from prior agents.", ("branch rule", "condition table", "fallback path"), DEFAULT_GUARDRAILS, ("pipeline_manager", "triage", "product_manager"), ("branch", "condition", "route")),
    AdvancedCapability("swarm_pipelines", "core_orchestration", "Swarm Pipelines", "Save and reuse named chains of agents for common workflows.", ("pipeline spec", "agent chain", "reuse instructions"), DEFAULT_GUARDRAILS, ("pipeline_manager", "documentation", "testing"), ("pipeline", "workflow", "chain")),
    AdvancedCapability("vector_memory", "memory_knowledge", "Vector Memory Agent", "Store factual project knowledge across runs and retrieve it by semantic similarity.", ("memory schema", "embedding plan", "retrieval policy"), DEFAULT_GUARDRAILS, ("vector_memory", "semantic_run_search", "auto_learner"), ("vector", "memory", "embedding")),
    AdvancedCapability("preference_memory", "memory_knowledge", "Long-Term User Preference Memory", "Learn the user's coding style, visual taste, naming preferences, and workflow choices over time.", ("preference profile", "confidence score", "update policy"), DEFAULT_GUARDRAILS, ("auto_learner", "hermes", "ux_research"), ("preference", "taste", "style", "learn")),
    AdvancedCapability("cross_session_handoff", "memory_knowledge", "Cross-Session Context Handoff", "Carry compact project state between separate runs without rereading the full codebase.", ("handoff summary", "pending work", "risk list"), DEFAULT_GUARDRAILS, ("checkpoint_manager", "documentation", "triage"), ("handoff", "cross session", "continue")),
    AdvancedCapability("hallucination_recovery", "memory_knowledge", "Hallucination Recovery", "Keep long sessions grounded by compacting verified state, separating facts from assumptions, and routing uncertain claims to evidence checks.", ("verified context packet", "assumption list", "evidence check plan"), DEFAULT_GUARDRAILS, ("hallucination_guard", "checkpoint_manager", "testing"), ("hallucination", "hallucinate", "long session", "stuck", "context drift")),
    AdvancedCapability("knowledge_graph_builder", "memory_knowledge", "Knowledge Graph Builder", "Map relationships between files, functions, agents, decisions, docs, and artifacts.", ("graph nodes", "graph edges", "architecture map"), DEFAULT_GUARDRAILS, ("knowledge_graph", "graphify", "documentation"), ("knowledge graph", "relationships", "architecture")),
    AdvancedCapability("semantic_run_search", "memory_knowledge", "Semantic Search Over Past Runs", "Find prior runs and decisions by meaning rather than exact filenames.", ("search query plan", "ranked run hits", "evidence snippets"), DEFAULT_GUARDRAILS, ("semantic_run_search", "vector_memory", "researcher"), ("past run", "semantic search", "find the run")),
    AdvancedCapability("diff_aware_agents", "code_dev", "Diff-Aware Agents", "Read only relevant git diffs for review and testing instead of scanning the whole repository.", ("diff scope", "affected files", "focused test plan"), DEFAULT_GUARDRAILS, ("diff_reviewer", "reviewer", "testing"), ("diff", "changed files")),
    AdvancedCapability("test_generator", "code_dev", "Dedicated Test Generator", "Generate pytest, Jest, Vitest, browser, and regression tests as a first-class workflow.", ("test cases", "fixtures", "coverage gaps"), DEFAULT_GUARDRAILS, ("test_generator", "testing", "app_tester"), ("pytest", "jest", "vitest", "test generator")),
    AdvancedCapability("migration_agent", "code_dev", "Migration Agent", "Plan database schema migrations, API version upgrades, and framework migrations.", ("migration plan", "rollback plan", "compatibility checks"), DEFAULT_GUARDRAILS, ("migration_agent", "backend_maker", "dependency_auditor"), ("migration", "schema", "upgrade")),
    AdvancedCapability("dependency_auditor", "code_dev", "Dependency Auditor", "Find outdated packages, CVEs, license conflicts, and risky transitive dependencies.", ("dependency report", "CVE list", "license conflicts"), DEFAULT_GUARDRAILS, ("dependency_auditor", "cve_monitor", "legal"), ("dependency", "cve", "license")),
    AdvancedCapability("code_explainer", "code_dev", "Code Explainer", "Create inline comments, architecture explanations, and onboarding notes for complex code.", ("explanation", "inline comment plan", "architecture notes"), DEFAULT_GUARDRAILS, ("code_explainer", "documentation", "writer"), ("explain", "inline comments", "onboarding")),
    AdvancedCapability("refactor_planner", "code_dev", "Refactor Planner", "Identify tech debt and break cleanup into low-risk incremental changes.", ("tech debt list", "refactor phases", "risk controls"), DEFAULT_GUARDRAILS, ("refactor_planner", "coder", "testing"), ("refactor", "tech debt")),
    AdvancedCapability("ci_cd_generator", "code_dev", "CI/CD Pipeline Generator", "Generate GitHub Actions, Vercel, Railway, Docker, and release pipeline plans.", ("workflow yaml plan", "deployment gates", "secrets checklist"), DEFAULT_GUARDRAILS, ("ci_cd_generator", "github_actions_runner", "docker_agent"), ("ci", "cd", "deploy", "github actions")),
    AdvancedCapability("model_trainer", "model_provider", "Model Trainer Integration", "Collect preference data, plan LoRA fine-tuning, and inject adapters for Ollama or LM Studio.", ("preference dataset", "LoRA plan", "adapter routing"), DEFAULT_GUARDRAILS, ("model_trainer", "auto_learner", "quantization_planner"), ("train", "lora", "fine tune")),
    AdvancedCapability("codex_caching", "model_provider", "Codex Caching System", "Cache stable project summaries, tool plans, and repeated context to reduce Codex token waste.", ("cache key", "cache policy", "invalidations"), DEFAULT_GUARDRAILS, ("codex_cache", "auto_learner", "checkpoint_manager"), ("cache", "codex caching")),
    AdvancedCapability("dynamic_model_benchmarking", "model_provider", "Dynamic Model Benchmarking", "Benchmark models against the user's real tasks and select winners for each role.", ("benchmark tasks", "model scores", "routing update"), DEFAULT_GUARDRAILS, ("dynamic_benchmark", "cost_optimizer", "provider_health_monitor"), ("benchmark", "models")),
    AdvancedCapability("model_cost_optimizer", "model_provider", "Model Cost Optimizer", "Pick the cheapest model that satisfies task quality, tool, modality, and context requirements.", ("cost-quality score", "chosen model", "fallback model"), DEFAULT_GUARDRAILS, ("cost_optimizer", "provider_health_monitor", "triage"), ("cheapest model", "optimize cost")),
    AdvancedCapability("quantization_planner", "model_provider", "Quantization Planner", "Recommend Q4/Q8 and context settings for local models based on user RAM and GPU/CPU limits.", ("quantization recommendation", "memory estimate", "local runtime notes"), DEFAULT_GUARDRAILS, ("quantization_planner", "model_trainer", "cost_optimizer"), ("quantization", "q4", "q8", "ram")),
    AdvancedCapability("provider_health_monitor", "model_provider", "Provider Health Monitor", "Track rate limits, outages, latency spikes, and error patterns in real time.", ("health status", "latency trend", "fallback trigger"), DEFAULT_GUARDRAILS, ("provider_health_monitor", "cost_dashboard", "triage"), ("provider health", "latency", "outage")),
    AdvancedCapability("playwright_integration", "browser_web", "Full Playwright Integration", "Plan real browser automation flows beyond basic snapshot and click tools.", ("browser scenario", "selectors", "assertions"), DEFAULT_GUARDRAILS, ("playwright_controller", "app_tester", "frontend_ui"), ("playwright", "browser automation")),
    AdvancedCapability("form_filler", "browser_web", "Form Filler Agent", "Fill and submit web forms with approval gates and field-level evidence.", ("field map", "submission plan", "approval gate"), DEFAULT_GUARDRAILS, ("form_filler", "browser_web", "legal"), ("form", "submit", "fill")),
    AdvancedCapability("site_monitor", "browser_web", "Site Monitor", "Watch URLs for changes and trigger swarm actions when configured signals appear.", ("watch list", "change rule", "trigger plan"), DEFAULT_GUARDRAILS, ("site_monitor", "web_scraper", "webhook_listener"), ("monitor site", "watch url")),
    AdvancedCapability("api_explorer", "browser_web", "API Explorer", "Discover and document REST or GraphQL endpoints from traffic, docs, or code.", ("endpoint inventory", "OpenAPI notes", "auth findings"), DEFAULT_GUARDRAILS, ("api_explorer", "backend_api", "documentation"), ("api explorer", "graphql", "rest")),
    AdvancedCapability("link_validator", "browser_web", "Link Validator", "Crawl project sites and docs to find broken links, redirects, and 404s.", ("broken link report", "redirect map", "fix list"), DEFAULT_GUARDRAILS, ("link_validator", "documentation", "app_tester"), ("broken link", "404", "crawl")),
    AdvancedCapability("secret_scanner", "security_safety", "Secret Scanner", "Scan agent outputs and changed files for hardcoded credentials before saving or committing.", ("secret scan report", "blocked patterns", "remediation notes"), DEFAULT_GUARDRAILS, ("secret_scanner", "security", "ai_reviewer"), ("secret", "api key", "credential")),
    AdvancedCapability("dependency_cve_monitor", "security_safety", "Dependency CVE Monitor", "Flag newly disclosed vulnerabilities in dependencies and generate patch plans.", ("CVE watch report", "affected packages", "upgrade plan"), DEFAULT_GUARDRAILS, ("cve_monitor", "dependency_auditor", "security"), ("cve monitor", "vulnerability")),
    AdvancedCapability("agent_sandboxing", "security_safety", "Agent Sandboxing", "Plan isolated containers or restricted runtimes for code execution agents.", ("sandbox policy", "allowed tools", "isolation plan"), DEFAULT_GUARDRAILS, ("sandbox_manager", "security", "docker_agent"), ("sandbox", "container isolation")),
    AdvancedCapability("output_diff_review", "security_safety", "Output Diff Review", "Show exactly what files changed after a swarm run with risk notes.", ("diff summary", "risk flags", "review checklist"), DEFAULT_GUARDRAILS, ("diff_reviewer", "reviewer", "ai_reviewer"), ("output diff", "changed")),
    AdvancedCapability("permission_escalation_alerts", "security_safety", "Permission Escalation Alerts", "Warn when an agent tries to access outside its declared file/tool/API scope.", ("permission event", "risk level", "user approval request"), DEFAULT_GUARDRAILS, ("permission_escalation_monitor", "security", "triage"), ("permission", "escalation", "outside scope")),
    AdvancedCapability("storyboard", "creative_media", "Storyboard Agent", "Plan visual narratives before video, animation, or mockup generation.", ("scene list", "shot timing", "asset list"), DEFAULT_GUARDRAILS, ("storyboard", "animator", "video_editor"), ("storyboard", "scene")),
    AdvancedCapability("brand_consistency", "creative_media", "Brand Consistency Agent", "Check outputs against brand colors, tone, typography, layout, and visual rules.", ("brand check", "violations", "fix suggestions"), DEFAULT_GUARDRAILS, ("brand_consistency", "design", "marketing"), ("brand", "guidelines")),
    AdvancedCapability("i18n_pipeline", "creative_media", "Multi-Language Localization Pipeline", "Coordinate full i18n content, UI, formatting, translation QA, and locale review.", ("locale matrix", "translation tasks", "QA checklist"), DEFAULT_GUARDRAILS, ("i18n_pipeline", "localization", "frontend_ui"), ("i18n", "localize", "translate")),
    AdvancedCapability("music_audio_generation", "creative_media", "Music / Audio Generation Planning", "Plan soundtracks, voice, SFX, captions, and audio export QA for video workflows.", ("audio brief", "SFX list", "mix checklist"), DEFAULT_GUARDRAILS, ("music_audio", "voice_generator", "video_editor"), ("music", "soundtrack", "sfx")),
    AdvancedCapability("ar_vr_scene_planner", "creative_media", "AR/VR Scene Planner", "Plan spatial scenes, interaction zones, assets, and comfort constraints for immersive work.", ("scene graph", "asset plan", "comfort checks"), DEFAULT_GUARDRAILS, ("ar_vr_planner", "building_designer", "animator"), ("ar", "vr", "spatial")),
    AdvancedCapability("game_developer", "creative_media", "Game Developer", "Plan and build playable game prototypes with engine selection, mechanics, controls, assets, performance budgets, and playtesting.", ("game design plan", "prototype task list", "playtest checklist"), DEFAULT_GUARDRAILS, ("game_developer", "storyboard", "app_tester"), ("game", "game developer", "playable", "unity", "godot", "phaser", "three.js")),
    AdvancedCapability("competitor_analysis", "business_act", "Competitor Analysis", "Scrape, compare, and summarize competitor products, positioning, and feature gaps.", ("competitor table", "gap analysis", "positioning notes"), DEFAULT_GUARDRAILS, ("competitor_analysis", "marketing", "web_scraper"), ("competitor", "market")),
    AdvancedCapability("seo_audit", "business_act", "SEO Audit", "Check technical SEO, meta tags, structured data, crawlability, and content gaps.", ("SEO report", "structured data checks", "fix list"), DEFAULT_GUARDRAILS, ("seo_audit", "marketing", "link_validator"), ("seo", "meta", "structured data")),
    AdvancedCapability("analytics_interpreter", "business_act", "Analytics Interpreter", "Read analytics exports and produce product, funnel, campaign, and growth insights.", ("insight report", "metric anomalies", "recommendations"), DEFAULT_GUARDRAILS, ("analytics_interpreter", "analytics", "marketing"), ("ga4", "mixpanel", "analytics")),
    AdvancedCapability("email_campaign", "business_act", "Email Campaign Planner", "Generate drip sequences, segmentation, subject lines, and experiment plans.", ("campaign sequence", "segments", "A/B ideas"), DEFAULT_GUARDRAILS, ("email_campaign", "marketing", "sales"), ("email campaign", "drip")),
    AdvancedCapability("invoice_contract", "business_act", "Invoice / Contract Generator", "Draft invoices, contracts, and clause templates with legal review gates.", ("document draft", "clause list", "approval notes"), DEFAULT_GUARDRAILS, ("invoice_contract", "legal", "finance"), ("invoice", "contract")),
    AdvancedCapability("pitch_deck", "business_act", "Pitch Deck Agent", "Generate investor deck structure from product, market, traction, and financial context.", ("slide outline", "data needs", "speaker notes"), DEFAULT_GUARDRAILS, ("pitch_deck", "finance", "marketing"), ("pitch deck", "investor")),
    AdvancedCapability("social_media_manager", "business_act", "Social Media Poster & Manager", "Create, approve, schedule, publish, monitor, and analyze social posts across major platforms.", ("content calendar", "post drafts", "approval queue", "engagement report"), DEFAULT_GUARDRAILS, ("social_media_manager", "marketing", "brand_consistency"), ("social media", "post", "schedule", "manager", "instagram", "linkedin", "tiktok", "youtube shorts")),
    AdvancedCapability("github_actions_runner", "integrations_ecosystem", "GitHub Actions Runner", "Trigger swarm checks on PRs and post council review summaries as comments.", ("workflow plan", "PR comment plan", "status checks"), DEFAULT_GUARDRAILS, ("github_actions_runner", "ci_cd_generator", "ai_reviewer"), ("github actions", "pr comment")),
    AdvancedCapability("webhook_listener", "integrations_ecosystem", "Webhook Listener", "Allow external services to kick off scoped swarm tasks through webhook events.", ("webhook route", "event schema", "auth plan"), DEFAULT_GUARDRAILS, ("webhook_listener", "rest_api_wrapper", "security"), ("webhook", "trigger")),
    AdvancedCapability("n8n_workflow_creator", "integrations_ecosystem", "n8n Workflow Creator", "Design importable n8n automation workflows with triggers, nodes, retries, credential mapping, dry-runs, and approval gates.", ("n8n workflow plan", "credential checklist", "dry-run payloads"), DEFAULT_GUARDRAILS, ("n8n_workflow_creator", "webhook_listener", "api_explorer"), ("n8n", "automation workflow", "workflow creator", "zapier alternative")),
    AdvancedCapability("chatops_bot", "integrations_ecosystem", "Slack / Discord Bot", "Run swarm commands from chat and post summarized results back.", ("command map", "bot permissions", "response template"), DEFAULT_GUARDRAILS, ("chatops_bot", "webhook_listener", "documentation"), ("slack", "discord", "chatops")),
    AdvancedCapability("notion_sync", "integrations_ecosystem", "Notion Sync", "Push outputs, decisions, docs, and run summaries to Notion pages or databases.", ("page schema", "sync plan", "conflict policy"), DEFAULT_GUARDRAILS, ("notion_sync", "documentation", "obsidian_sync"), ("notion", "sync")),
    AdvancedCapability("issue_tracker", "integrations_ecosystem", "Linear / Jira Integration", "Create tickets from triage and update issue states when work completes.", ("ticket fields", "workflow states", "update rules"), DEFAULT_GUARDRAILS, ("issue_tracker", "product_manager", "triage"), ("linear", "jira", "ticket")),
    AdvancedCapability("supabase_agent", "integrations_ecosystem", "Supabase Agent", "Plan schemas, RLS policies, auth, storage, edge functions, and Supabase migrations.", ("schema plan", "RLS policy plan", "edge function notes"), DEFAULT_GUARDRAILS, ("supabase_agent", "backend_maker", "security"), ("supabase", "rls")),
    AdvancedCapability("stripe_agent", "integrations_ecosystem", "Stripe Integration Agent", "Plan payment flows, webhooks, checkout, billing, tests, and security boundaries.", ("payment flow", "webhook plan", "test matrix"), DEFAULT_GUARDRAILS, ("stripe_agent", "backend_api", "finance"), ("stripe", "payment")),
    AdvancedCapability("docker_agent", "integrations_ecosystem", "Docker Agent", "Generate Dockerfiles, compose files, container optimization, and runtime checks.", ("Dockerfile plan", "compose plan", "image hardening notes"), DEFAULT_GUARDRAILS, ("docker_agent", "ci_cd_generator", "sandbox_manager"), ("docker", "compose", "container")),
    AdvancedCapability("otel_tracing", "observability_monitoring", "OpenTelemetry Tracing", "Represent every agent turn as a trace span exportable to Grafana, Jaeger, or OTLP collectors.", ("span schema", "exporter plan", "trace IDs"), DEFAULT_GUARDRAILS, ("telemetry_tracer", "performance_leaderboard", "cost_dashboard"), ("opentelemetry", "otel", "trace")),
    AdvancedCapability("real_time_cost_dashboard", "observability_monitoring", "Real-Time Cost Dashboard", "Track live token spend, provider latency, and cost per agent per run.", ("cost stream", "dashboard panels", "budget alerts"), DEFAULT_GUARDRAILS, ("cost_dashboard", "cost_optimizer", "provider_health_monitor"), ("cost dashboard", "token spend")),
    AdvancedCapability("agent_performance_leaderboard", "observability_monitoring", "Agent Performance Leaderboard", "Rank agents by speed, success rate, cost, quality, and retry rate.", ("leaderboard metrics", "baseline scores", "improvement hints"), DEFAULT_GUARDRAILS, ("performance_leaderboard", "anomaly_detector", "analytics"), ("leaderboard", "performance")),
    AdvancedCapability("run_diff_viewer", "observability_monitoring", "Run Diff Viewer", "Compare two swarm runs side by side across agents, costs, outputs, and decisions.", ("run comparison", "changed decisions", "cost delta"), DEFAULT_GUARDRAILS, ("run_diff_viewer", "replay_runner", "analytics"), ("run diff", "compare runs")),
    AdvancedCapability("anomaly_detector", "observability_monitoring", "Anomaly Detector", "Flag agents behaving unusually versus baseline latency, token, tool, or output patterns.", ("anomaly event", "baseline delta", "recommended action"), DEFAULT_GUARDRAILS, ("anomaly_detector", "provider_health_monitor", "security"), ("anomaly", "unusual")),
    AdvancedCapability("vscode_extension", "developer_experience", "VS Code Extension", "Plan editor sidebar commands, status views, and local run controls.", ("extension command map", "views", "activation plan"), DEFAULT_GUARDRAILS, ("vscode_extension", "typescript_sdk", "rest_api_wrapper"), ("vscode", "extension")),
    AdvancedCapability("swarm_builder_ui", "developer_experience", "Interactive Swarm Builder UI", "Plan drag-and-drop agent chains and visual workflow editing.", ("UI model", "node types", "save format"), DEFAULT_GUARDRAILS, ("swarm_builder_ui", "frontend_ui", "pipeline_manager"), ("builder ui", "drag and drop")),
    AdvancedCapability("agent_marketplace", "developer_experience", "Agent Marketplace", "Plan community custom agents, ratings, manifests, moderation, and install flow.", ("marketplace schema", "rating rules", "install plan"), DEFAULT_GUARDRAILS, ("agent_marketplace", "security", "documentation"), ("marketplace", "custom agents")),
    AdvancedCapability("cloud_deploy", "developer_experience", "One-Command Cloud Deploy", "Plan hosted API deployment for Agent Swarm with auth, workers, and observability.", ("deploy plan", "infra checklist", "rollback plan"), DEFAULT_GUARDRAILS, ("cloud_deploy", "docker_agent", "ci_cd_generator"), ("cloud deploy", "hosted api")),
    AdvancedCapability("typescript_sdk", "developer_experience", "TypeScript SDK", "Plan a JS/TS client for running swarm tasks without Python.", ("SDK surface", "types", "examples"), DEFAULT_GUARDRAILS, ("typescript_sdk", "rest_api_wrapper", "documentation"), ("typescript", "sdk", "javascript")),
    AdvancedCapability("rest_api_wrapper", "developer_experience", "REST API Wrapper", "Expose Agent Swarm through HTTP endpoints for external tools.", ("route plan", "request schema", "auth guardrails"), DEFAULT_GUARDRAILS, ("rest_api_wrapper", "backend_api", "security"), ("rest api", "http api")),
)


def list_advanced_capabilities(category: str | None = None) -> list[dict]:
    selected = CAPABILITIES
    if category:
        category_lower = category.strip().lower()
        selected = tuple(item for item in CAPABILITIES if item.category.lower() == category_lower)
    return [item.to_dict() for item in selected]


def plan_advanced_capability(task: str, capability: str = "auto") -> dict:
    selected = _select_capability(task, capability)
    return {
        "capability": selected.to_dict(),
        "task": task,
        "phases": [
            "clarify inputs, scope, approval gates, and success metrics",
            "assign primary and helper agents",
            "produce a dry-run plan with expected artifacts and cost/risk notes",
            "execute only approved actions with scoped tools and checkpoints",
            "run tests or validation, then save replayable evidence",
        ],
        "primary_agent": selected.suggested_agents[0],
        "helper_agents": list(selected.suggested_agents[1:]),
        "approval_gates": [
            "external writes or submissions",
            "credential or payment changes",
            "destructive file/database operations",
            "publishing, deployment, or notification fan-out",
        ],
    }


def build_auto_learner_profile(events: str, scope: str = "project") -> dict:
    text = " ".join(str(events or "").split())
    lower = text.lower()
    preferences = []
    for keyword, preference in (
        ("dark", "prefers dark UI when suitable"),
        ("test", "values aggressive regression testing"),
        ("fast", "prefers low-lag workflows"),
        ("cheap", "prefers token and provider cost control"),
        ("video", "cares about visual demo quality"),
        ("graph", "likes connected graph visualizations"),
        ("readme", "expects README and public-facing docs to stay updated"),
    ):
        if keyword in lower:
            preferences.append(preference)
    if not preferences:
        preferences.append("no strong preference inferred yet")
    return {
        "agent": "auto_learner",
        "scope": scope,
        "learned_preferences": preferences,
        "confidence": min(95, 55 + 8 * len([p for p in preferences if not p.startswith("no strong")])),
        "memory_policy": {
            "requires_user_approval_for_durable_user_memory": True,
            "store_project_patterns_without_secrets": True,
            "forget_or_update_when_user_corrects_preference": True,
        },
        "next_prompt_additions": [f"Respect: {preference}" for preference in preferences if not preference.startswith("no strong")],
    }


def build_swarm_pipeline(name: str, agents: str, goal: str) -> dict:
    chain = [agent.strip() for agent in agents.split(",") if agent.strip()]
    return {
        "name": name.strip() or "custom_pipeline",
        "goal": goal,
        "agents": chain,
        "execution": {
            "parallelizable": chain[1:-1] if len(chain) > 2 else [],
            "requires_council_before_start": True,
            "requires_master_review_after_finish": True,
            "checkpoint_after_each_agent": True,
        },
        "artifacts": ["pipeline_manifest", "run_replay_log", "master_review"],
    }


def _select_capability(task: str, capability: str) -> AdvancedCapability:
    requested = capability.strip().lower()
    for item in CAPABILITIES:
        if requested in {item.key.lower(), item.title.lower()}:
            return item
    text = f"{task} {capability}".lower()
    scored = []
    for item in CAPABILITIES:
        score = sum(2 for trigger in item.triggers if trigger.lower() in text)
        score += sum(1 for token in item.title.lower().split() if token in text)
        score += 1 if item.category.replace("_", " ") in text else 0
        scored.append((score, item))
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return scored[0][1] if scored and scored[0][0] > 0 else CAPABILITIES[0]
