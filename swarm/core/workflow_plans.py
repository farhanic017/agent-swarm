from __future__ import annotations


def build_web_scraper_plan(target: str, goal: str = "extract useful data") -> dict:
    return {
        "type": "web_scraper",
        "target": target,
        "goal": goal,
        "steps": [
            "check robots, terms, rate limits, and whether an official API exists",
            "open the page with browser tools when JavaScript rendering is required",
            "extract structured fields with selectors or network-observed APIs",
            "deduplicate, normalize, and validate records",
            "export CSV/JSON plus source URLs and timestamps",
        ],
        "guardrails": {
            "rate_limit": True,
            "prefer_official_api": True,
            "respect_auth_boundaries": True,
            "store_sources": True,
        },
    }


def build_job_finder_applier_plan(query: str, profile_summary: str = "", mode: str = "find") -> dict:
    apply_mode = mode.lower() in {"apply", "find_and_apply", "applier"}
    return {
        "type": "job_finder_applier",
        "query": query,
        "mode": "find_and_apply" if apply_mode else "find_only",
        "steps": [
            "find matching jobs across selected boards, company sites, and recruiter pages",
            "score each job for fit, compensation hints, location, remote policy, and required skills",
            "tailor resume bullets and cover notes from approved user profile facts",
            "prepare application drafts and required field answers",
            "submit only after explicit user approval for each application",
        ],
        "profile_summary": profile_summary,
        "guardrails": {
            "no_false_claims": True,
            "user_approval_before_submit": True,
            "track_application_log": True,
            "avoid_duplicate_applications": True,
        },
    }


def build_building_design_plan(prompt: str, scope: str = "interior_and_exterior") -> dict:
    return {
        "type": "building_interior_exterior_designer",
        "prompt": prompt,
        "scope": scope,
        "steps": [
            "extract site, floor-plan, dimensions, rooms, facade, circulation, lighting, and material requirements",
            "produce exterior massing, facade, landscape, entrance, and window/door direction",
            "produce interior layout, furniture zones, lighting, finishes, storage, and accessibility notes",
            "create 2D plan notes plus 3D blockout/render plan for Blender, Three.js, or design tools",
            "run visual QA for scale, collisions, circulation, and design consistency",
        ],
        "outputs": ["moodboard_notes", "floor_plan_notes", "exterior_direction", "interior_direction", "3d_model_plan"],
        "guardrails": {
            "ask_for_dimensions_in_plan_mode": True,
            "flag_structural_engineering_needs": True,
            "separate_concept_design_from_permitted_construction_docs": True,
        },
    }


def build_app_tester_plan(app: str, focus: str = "full QA") -> dict:
    return {
        "type": "app_tester",
        "app": app,
        "focus": focus,
        "steps": [
            "map core user flows and high-risk state transitions",
            "run unit, integration, browser, accessibility, responsive, and performance checks",
            "test auth, data validation, file uploads, payments, and external APIs when present",
            "capture screenshots, console/network errors, and reproduction steps",
            "send issues to the responsible build/backend/frontend agent before final integration",
        ],
        "test_types": ["unit", "integration", "e2e", "accessibility", "responsive", "performance", "security_smoke"],
    }


def build_app_builder_plan(prompt: str, stack: str = "auto") -> dict:
    return {
        "type": "app_builder",
        "prompt": prompt,
        "stack": stack,
        "steps": [
            "turn the request into requirements, routes, data models, states, and acceptance tests",
            "build frontend, backend, persistence, auth, and integrations with specialist agents",
            "wire generated parts together and run master integration review",
            "create install/run docs and smoke-test commands",
            "deliver dashboard/test evidence and remaining risks",
        ],
        "sub_agents": ["product_manager", "frontend_ui", "backend_maker", "app_tester", "security", "documentation"],
    }


def build_backend_maker_plan(prompt: str, framework: str = "auto") -> dict:
    return {
        "type": "backend_maker",
        "prompt": prompt,
        "framework": framework,
        "steps": [
            "define API contracts, schemas, auth, validation, permissions, and error handling",
            "implement routes/services/data access with migration or storage notes",
            "add rate limits, audit logs, input validation, and secret-safe config",
            "write backend unit/integration tests and OpenAPI-style docs when applicable",
            "handoff to app tester and master review before release",
        ],
        "guardrails": {
            "least_privilege_auth": True,
            "validate_inputs": True,
            "no_hardcoded_secrets": True,
            "migration_review": True,
        },
    }
